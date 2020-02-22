try:
    from regex._regex_core import error
    import regex as re

    def parse_name(source, allow_numeric=False, allow_group_0=False):
        "Parses a name."
        name = source.get_while(set(")>"), include=False)

        if not name:
            raise error("missing group name", source.string, source.pos)

        if name.isdigit():
            min_group = 0 if allow_group_0 else 1
            if not allow_numeric or int(name) < min_group:
                raise error("bad character in group name", source.string,
                  source.pos)
        else:
            if not name.replace("@", "").replace(".","").isidentifier():
                raise error("character in group name", source.string,
                  source.pos)

        return name

    # this allows dots in the group names
    re._regex_core.parse_name = parse_name

except ImportError:
    # If you import re, grok_match can't handle regular expression containing atomic group(?>)
    import re

import codecs
import os
import pkg_resources

DEFAULT_PATTERNS_DIRS = [pkg_resources.resource_filename(__name__, "patterns")]


class Grok(object):
    def __init__(
        self,
        pattern,
        custom_patterns_dir=None,
        custom_patterns=None,
        fullmatch=True,
        match_unnamed_groks=False,
       flags=0
    ):
        self.pattern = pattern
        self.custom_patterns_dir = custom_patterns_dir
        self.predefined_patterns = _reload_patterns(DEFAULT_PATTERNS_DIRS)
        self.fullmatch = fullmatch
        custom_patterns = custom_patterns or {}
        self.match_unnamed_groks = match_unnamed_groks
        self.flags = flags

        custom_pats = {}
        if custom_patterns_dir is not None:
            custom_pats = _reload_patterns([custom_patterns_dir])

        for pat_name, regex_str in custom_patterns.items():
            custom_pats[pat_name] = Pattern(pat_name, regex_str)

        if len(custom_pats) > 0:
            self.predefined_patterns.update(custom_pats)

        self._load_search_pattern()

    def match(self, text):
        """If text is matched with pattern, return variable names specified(%{pattern:variable name})
        in pattern and their corresponding values.If not matched, return None.
        custom patterns can be passed in by custom_patterns(pattern name, pattern regular expression pair)
        or custom_patterns_dir.
        """
        if self.fullmatch:
            match_obj = self.regex_obj.fullmatch(text)
        else:
            match_obj = self.regex_obj.search(text)

        if match_obj == None:
            return None
        matches = match_obj.groupdict()
        for key, match in matches.items():
            try:
                if self.type_mapper[key] == "int":
                    matches[key] = int(match)
                if self.type_mapper[key] == "float":
                    matches[key] = float(match)
            except (TypeError, KeyError):
                pass
        return unflatten(matches)

    def set_search_pattern(self, pattern=None):
        if type(pattern) is not str:
            raise ValueError("Please supply a valid pattern")
        self.pattern = pattern
        self._load_search_pattern()

    def _load_search_pattern(self):
        self.type_mapper = {}
        py_regex_pattern = self.pattern
        while True:
            # Finding all types specified in the groks
            m = re.findall(r"%{(\w+):([@\w\.?\[\]]+):(\w+)}", py_regex_pattern)
            for n in m:
                # accounts for dotted or legacy groups, but not both at the same time
                key =  '.'.join([f[1] and f[1] or f[0] for f in re.findall("\[([@\.\w]*?)\]|([@\.\w]+)", n[1])])
                self.type_mapper[key] = n[2]
            # replace %{pattern_name:custom_name} (or %{pattern_name:custom_name:type}
            # with regex and regex group name

            py_regex_pattern = re.sub(
                r"%{(\w+):(\[?[@\w\]\[\.]+\]?)(?::\w+)?}",
                lambda m: "(?P<"
                + m.group(2).replace("][", ".").replace("[", "").replace("]", "")
                + ">"
                + self.predefined_patterns[m.group(1)].regex_str
                + ")",
                py_regex_pattern,
            )

            # replace %{pattern_name} with regex
            if self.match_unnamed_groks:
                sub_method = (
                    lambda m: "(?P<"
                    + m.group(1)
                    + ">"
                    + self.predefined_patterns[m.group(1)].regex_str
                    + ")"
                )
            else:
                sub_method = (
                    lambda m: "(" + self.predefined_patterns[m.group(1)].regex_str + ")"
                )
            py_regex_pattern = re.sub(
                r"%{(\w+)}",
                sub_method,
                py_regex_pattern,
            )

            if re.search("%{\w+(:[@\w\.?\[\]]+)?}", py_regex_pattern) is None:
                break

        self.regex_obj = re.compile(py_regex_pattern, flags=self.flags)


def _wrap_pattern_name(pat_name):
    return "%{" + pat_name + "}"


def _reload_patterns(patterns_dirs):
    """ """
    all_patterns = {}
    for dir in patterns_dirs:
        for f in os.listdir(dir):
            patterns = _load_patterns_from_file(os.path.join(dir, f))
            all_patterns.update(patterns)

    return all_patterns


def _load_patterns_from_file(file):
    """ """
    patterns = {}
    with codecs.open(file, "r", encoding="utf-8") as f:
        for l in f:
            l = l.strip()
            if l == "" or l.startswith("#"):
                continue

            sep = l.find(" ")
            pat_name = l[:sep]
            regex_str = l[sep:].strip()
            pat = Pattern(pat_name, regex_str)
            patterns[pat.pattern_name] = pat
    return patterns


def unflatten(dictionary, nullable=False):
    resultDict = dict()
    for key, value in dictionary.items():
        if nullable or value is not None:
            parts = key.split(".")
            d = resultDict
            for part in parts[:-1]:
                if part not in d:
                    d[part] = dict()
                d = d[part]
            d[parts[-1]] = value
    return resultDict


class Pattern(object):
    """ """

    def __init__(self, pattern_name, regex_str, sub_patterns=None):
        self.pattern_name = pattern_name
        self.regex_str = regex_str
        self.sub_patterns = sub_patterns or {}  # sub_pattern name list

    def __str__(self):
        return "<Pattern:%s,  %s,  %s>" % (
            self.pattern_name,
            self.regex_str,
            self.sub_patterns,
        )



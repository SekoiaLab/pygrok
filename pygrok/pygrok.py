import codecs
import os
from functools import cache
from importlib import resources

import re2 as re

DEFAULT_PATTERNS_DIRS = str(resources.files(__name__) / "patterns")


max_mem = int(os.getenv("RE2_MAX_MEM", 100 << 20))


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


class Grok(object):
    def __init__(
        self,
        pattern,
        custom_patterns=None,
        fullmatch=True,
        match_unnamed_groks=False,
    ):
        self.fullmatch = fullmatch

        base_patterns = _reload_patterns(DEFAULT_PATTERNS_DIRS)

        if custom_patterns:
            # Create a copy to avoid altering the cached version
            base_patterns = base_patterns.copy()

            for pat_name, regex_str in custom_patterns.items():
                base_patterns[pat_name] = Pattern(pat_name, regex_str)

        self._load_search_pattern(pattern, base_patterns, match_unnamed_groks)

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

        if match_obj is None:
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

        return matches

    def _load_search_pattern(self, pattern, base_patterns, match_unnamed_groks):
        self.type_mapper = {}
        py_regex_pattern = pattern
        while True:
            # Finding all types specified in the groks
            m = re.findall(r"%{(\w+):(\w+):(\w+)}", py_regex_pattern)
            for n in m:
                self.type_mapper[n[1]] = n[2]
            # replace %{pattern_name:custom_name} (or %{pattern_name:custom_name:type}
            # with regex and regex group name

            py_regex_pattern = re.sub(
                r"%{(\w+):(\w+)(?::\w+)?}",
                lambda m: "(?P<"
                + m.group(2)
                + ">"
                + base_patterns[m.group(1)].regex_str
                + ")",
                py_regex_pattern,
            )

            # replace %{pattern_name} with regex
            if match_unnamed_groks:
                sub_method = (
                    lambda m: "(?P<"
                    + m.group(1)
                    + ">"
                    + base_patterns[m.group(1)].regex_str
                    + ")"
                )
            else:
                sub_method = lambda m: "(" + base_patterns[m.group(1)].regex_str + ")"
            py_regex_pattern = re.sub(r"%{(\w+)}", sub_method, py_regex_pattern)

            if re.search(r"%{\w+(:\w+)?}", py_regex_pattern) is None:
                break

        self.regex_obj = re.compile(py_regex_pattern, max_mem=max_mem)


@cache
def _reload_patterns(patterns_dir):
    """ """
    all_patterns = {}

    for f in os.listdir(patterns_dir):
        patterns = _load_patterns_from_file(os.path.join(patterns_dir, f))
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

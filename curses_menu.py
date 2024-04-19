"""
https://wasimlorgat.com/posts/editor
https://hyperskill.org/blog/post/introduction-to-the-curses-library-in-python-text-based-interfaces
https://stackoverflow.com/questions/18551558/how-to-use-terminal-color-palette-with-curses
"""

import sys
import re
from copy import deepcopy

import os
os.environ.setdefault('ESCDELAY', '25')
# ESC has a special delay to capture any valid escape sequence...
KEY_ESC = 27
KEY_CTRLW = 23
# it also has a problem of confusing esc and alt...
# esc = 27
# alt A = 27 65 ...
# https://stackoverflow.com/questions/5977395/ncurses-and-esc-alt-keys
# the way to handle it:
# elif key == 27: # Esc or Alt
#     # Don't wait for another key
#     # If it was Alt then curses has already sent the other key
#     # otherwise -1 is sent (Escape)
#     self.screen.nodelay(True)
#     n = self.screen.getch()
#     if n == -1:
#         # Escape was pressed
#         go = False
#     # Return to delay
#     self.screen.nodelay(False)
# but it still needs the low delay!

import curses
from curses import wrapper
from curses.textpad import Textbox, rectangle

selected_opts = set()

'''
I aim at the Quasar OPC Design.xml
it is very simple:
    <tag_of_class_variable has_state=V> <and_chidren_tags...> </tag>
    <tag_class> <is a device, it contains other tags and has no state> </tag>

Probably, it would be good to just deal with an XML/HTML object?
But it must be done without an external library, like beautifulsoup.
Such a simple structure can be done in JSON too.
If needed, it can be extended to some TOML, if needed.

Let's focus this on working with structured nested data, XML.
Not any plain test like grep.
The problem is, the option should be given with full-path,
not just the current tag.

Let's do it slowly. First, a simple dict.

It unfolds into simple:
    [list, of, strings, with, DP, names]: value
Or no value in some cases. I want to search by names, but also by values.

... it is also true that variables do not have children tags here...
We have a very simple tree where branches are devices with no state,
and leaves are variables with state and no nested children.
So, it is exactly like the recursive iteration function for dictionaries.

I need a selector for sibling value. I.e. to select DP Enable
who has a sibling whose value is "PPB1A", i.e. that's the connectivity nickname.

Do I need to invert the selection algorithm?
I.e. now each pattern filters the list of options. I.e. the patterns act on
individual options, independently from the other ones. But it should be inverted,
where the whole line of patterns is matched to each option.
This way we'll get the search relative to siblings and parent node.
'''

xml_options = '''<?xml version="1.0"?>
<data>
    <country name="Liechtenstein">
        <rank>1</rank>
        <year>2008</year>
        <gdppc>141100</gdppc>
        <neighbor name="Austria" direction="E"/>
        <neighbor name="Switzerland" direction="W"/>
    </country>
    <country name="Singapore">
        <rank>4</rank>
        <year>2011</year>
        <gdppc>59900</gdppc>
        <neighbor name="Malaysia" direction="N"/>
    </country>
    <country name="Panama">
        <rank>68</rank>
        <year>2011</year>
        <gdppc>13600</gdppc>
        <neighbor name="Costa Rica" direction="W"/>
        <neighbor name="Colombia" direction="E"/>
    </country>
    <nested value="2" type="int"></nested>
    <struct>
        <bar value="3"></bar>
        <baz value="5"></baz>
    </struct>
    <just value="5"></just>
    <Just value="5"></Just>
    <foo>
        <Bar value="77"></Bar>
        <bar>
        </bar>
    </foo>
</data>
'''

from collections import namedtuple
MatchString = namedtuple('MatchString', 'content ismatch')
_DataPoint  = namedtuple('DataPoint', 'path value', defaults=(None, None))
class DataPoint(_DataPoint):
    def __str__(self):
        return f'{self.path}={self.value}'

OptionPath = namedtuple('OptionPath', 'path options')
# path is a list of match strings
# options is a dictionary

'''
make a matched string to highlight in curses
'''
class MatchStringL:
    def __init__(self, arg, default_match=False):
        if   isinstance(arg, str):
            self.match_strings = [MatchString(arg, default_match)]
        elif isinstance(arg, list):
            self.match_strings = []
            for s in arg:
                self.match_strings.append(s if isinstance(s, MatchString) else MatchString(str(s), default_match))
        else:
            raise TypeError(f"arg must be str or list of MatchString, it is {type(arg)}")
    def __str__(self):
        return ''.join(f'{s.content}' for s in self.match_strings)
    def __repr__(self):
        return f'MatchStringL("{self}")'
    def __add__(self, other):
        assert isinstance(other, MatchStringL)
        return MatchStringL(self.match_strings + other.match_strings)
    # def print_to_curses(self, stdscr, line_num, char_pos, line_option, styleMatchedText, styleNormalText):
    def print_to_curses(self, stdscr, line_option, styleMatchedText, styleNormalText, coord=None):
        # Print the matched options
        #stdscr.addstr(line_num, char_pos, select_prompt)
        if coord is not None:
            line_num, char_pos = coord
            stdscr.move(line_num, char_pos)
        for substr in self.match_strings:
            opt = line_option | (styleMatchedText if substr.ismatch else styleNormalText)
            stdscr.addstr(substr.content, opt)

opts = 'klasd qwe pod 34 kjnd temp pre foo fuz toopoomoobooo'.split()

def iteritems_recursive(d):
    for k,v in d.items():
      if isinstance(v, dict):
        for k1,v1 in iteritems_recursive(v):
          yield (k,)+k1, v1
      else:
        yield (k,),v

some_nested_structure = {'some':
        {'nested': 2, 'struct': {'bar': 3, 'baz': 5}},
        'just': 5,
        'Just': 5,
        'foo': {'Bar': 77, 'bar': {'foo': 88, 'ccc': {'qwe': 5, 'enable': True, 'bar': 18}, 'baz': 'work'}},
        'Foo': {72: 'Bar', 'bar': {'baz': 88}},
        'and_cases': {'foo': {'bar': 88}, 'baz': {'Bar': 55}},
        'more': {'nestings': 67, 5: 'five'},
        'and': 'only_string',
        'only_strings': {'foo': 'bar', 'baz': 'qwe',
            'plus': {'and': 'five', 'more': 'less'},
            'Connectivity': 'PPB1A'},
        }

opts = []
for p, v in iteritems_recursive(some_nested_structure):
    #print(f'{p} -> {v}')
    #opts.append('.'.join([str(i) for i in p]) + '=' + str(v))
    opts.append(DataPoint('.'.join([str(i) for i in p]), v))

opts = [OptionPath([], some_nested_structure)]

def flatten_opt_paths(opt_paths):
    flat_opts = []
    for path, opts in opt_paths:
        for p, v in iteritems_recursive(opts):
            flat_opts.append((path + list(p), v))

    return flat_opts

'''
OptionTagRaw = namedtuple('OptionTag', 'name value type', defaults=('tag', None, None))
class OptionTag(OptionTagRaw):
    def __str__(self):
        return str(self.name)
OT = OptionTag

some_nested_tags = {OptionTag('some'):
        {OptionTag('nested'): OT(2),
         OptionTag('struct', 3): {OptionTag('baz'): OT(5)}},
        OptionTag('just'): OT(5),
        OptionTag('Just'): OT(5),
        OptionTag('Sys'): {OT('stave'): {OT('Connectivity', 'PPB1A'): None, OT('Enabled', 'False'): None, 'bus': {'AMAC': 5}}},
        OptionTag('foo'): {OT('Bar'): OT(77), OT('bar'): {'foo': 88}},
        OptionTag('Foo'): {72: 'Bar', 'bar': {'baz': 88}},
        OptionTag('more'): {'nestings': 67, 5: 'five'},
        OptionTag('and'): 'only_string',
        OptionTag('only_strings'): {'foo': 'bar', 'baz': 'qwe'}
        }

opts = []
for p,v in iteritems_recursive(some_nested_tags):
    #print(f'{p} -> {v}')
    opt_str = '.'.join([str(i) for i in p])
    if v is not None:
        opt_str += '.' + str(v)
    if isinstance(v, OptionTag) and v.value is not None:
        opt_str += '=' + str(v.value)
    opts.append(opt_str)
'''

DEBUG = True

FIELD_SEPARATOR='.'

def match_string_to_substr_selector(substr):
  def selector(cur_matches: list, stdscr, prev_offset, debug_line) -> list:
    # the string matcher works on the current reminder
    last_substr = cur_matches[-1].content

    if substr.upper() not in last_substr.upper():
        return None

    ind = last_substr.upper().index(substr.upper())
    pre, matched, post = last_substr[:ind], last_substr[ind:ind+len(substr)], last_substr[ind+len(substr):]
    matches = cur_matches[:-1] + [MatchString(pre, False)] + [MatchString(matched, True)] + [MatchString(post, False)]

    if DEBUG:
        stdscr.addstr(20+debug_line, prev_offset, f'{last_substr} - {ind} - {matches}')
        prev_offset += 1 + len(last_substr)

    return matches

  return selector

basic_type_keywords = {
        'int': lambda s: s.isnumeric()
        }

def match_string_field_to_basic_type(selector_keyword: str):
  type_selector = basic_type_keywords.get(selector_keyword)
  if type_selector is None:
      return match_string_to_substr_selector(selector_keyword)

  def selector(cur_matches: list, stdscr, prev_offset, debug_line) -> list:
    # match the string fields
    # a "field" is a .-separated part in the string
    # for simplicity let's start from the next "complete field"
    # i.e. the one that was not touched by the previous selectors
    last_substr = cur_matches[-1].content
    if len(cur_matches)>1 and cur_matches[-2].content[-1] != FIELD_SEPARATOR:
        # then the selector matching stopped in the middle of a field
        cutoff, *fields = last_substr.split(FIELD_SEPARATOR)

    else:
        fields = last_substr.split(FIELD_SEPARATOR)
        cutoff = None

    # find the first one that matches
    #if any(selector(f) for f in fields)
    matched_field_i = None
    for i, f in enumerate(fields):
        if type_selector(f):
            matched_field_i = i

    if DEBUG:
        #prev_offset += 1 + len(last_substr)
        stdscr.addstr(20+debug_line, prev_offset, f'None: {last_substr} -> {cutoff} {fields}')
        #prev_offset += 5 + len('None')

    if matched_field_i is None: # the matching failed for this option
        # if there were no fields, i.e. the whole last string was a cutoff
        # it fails too

        return None

    # reassamble the fields back into strings
    # and mark the matching field
    match_field = fields[matched_field_i]
    new_matches = []
    if cutoff:
        pre = FIELD_SEPARATOR.join([cutoff] + fields[:matched_field_i])
    else:
        pre = FIELD_SEPARATOR.join(fields[:matched_field_i])

    post = FIELD_SEPARATOR.join(fields[matched_field_i+1:])
    if post: # if not empty
        post = FIELD_SEPARATOR + post

    new_matches.append(MatchString(pre + FIELD_SEPARATOR, False))
    new_matches.append(MatchString(match_field, True))
    new_matches.append(MatchString(post, False))

    return cur_matches[:-1] + new_matches

  return selector

def match_string_field_child(child_substr: str):
    def selector(cur_matches: list, stdscr, prev_offset, debug_line) -> list:
        # check if the child field contains child_substr
        last_substr = cur_matches[-1].content

        cutoff = None
        if len(cur_matches)>1 and cur_matches[-2].content[-1] == FIELD_SEPARATOR:
            # the child field starts from the start of the last_substr
            fields = last_substr.split(FIELD_SEPARATOR)

        elif FIELD_SEPARATOR not in last_substr:
            # i.e. the case when the matching cursor sits
            # in the middle of the last field
            # -- no child fields at this point
            return None

        else:
            cutoff, *fields = last_substr.split(FIELD_SEPARATOR)

        child_field = fields[0]

        if DEBUG:
            #prev_offset += 1 + len(last_substr)
            stdscr.addstr(20+debug_line, prev_offset, f'None: {last_substr} -> {cutoff} {fields} | {child_field}')
            #prev_offset += 5 + len('None')

        if child_substr not in child_field:
            return None

        # make the list of matches
        ind = child_field.index(child_substr)
        pre, post = child_field[:ind], child_field[ind+len(child_substr):]

        # add the cutoff to pre, if needed
        if cutoff is not None:
            pre = cutoff + '.' + pre

        post = '.'.join([post] + fields[1:])

        matches = cur_matches[:-1] + [MatchString(pre, False)] + [MatchString(child_substr, True)] + [MatchString(post, False)]

        return matches

    return selector

def match_string_field_sibling_value(value: str):
    def selector(cur_matches: list, stdscr, prev_offset, debug_line) -> list:
        # check if the siblings contain a field with the value
        # ...
        # it needs the whole tree of options
        last_substr = cur_matches[-1].content

        cutoff = None
        if len(cur_matches)>1 and cur_matches[-2].content[-1] == FIELD_SEPARATOR:
            # the child field starts from the start of the last_substr
            fields = last_substr.split(FIELD_SEPARATOR)

        elif FIELD_SEPARATOR not in last_substr:
            # i.e. the case when the matching cursor sits
            # in the middle of the last field
            # -- no child fields at this point
            return None

        else:
            cutoff, *fields = last_substr.split(FIELD_SEPARATOR)

        child_field = fields[0]

        if DEBUG:
            #prev_offset += 1 + len(last_substr)
            stdscr.addstr(20+debug_line, prev_offset, f'None: {last_substr} -> {cutoff} {fields} | {child_field}')
            #prev_offset += 5 + len('None')

        if child_substr not in child_field:
            return None

        # make the list of matches
        ind = child_field.index(child_substr)
        pre, post = child_field[:ind], child_field[ind+len(child_substr):]

        # add the cutoff to pre, if needed
        if cutoff is not None:
            pre = cutoff + '.' + pre

        post = '.'.join([post] + fields[1:])

        matches = cur_matches[:-1] + [MatchString(pre, False)] + [MatchString(child_substr, True)] + [MatchString(post, False)]

        return matches

    return selector


def dispatch_selectors(selector_string: str):

    if selector_string[0] == '.':
        return match_string_field_to_basic_type(selector_string[1:])

    elif selector_string[0] == '>':
        return match_string_field_child(selector_string[1:])

    return match_string_to_substr_selector(selector_string)

def match_string_to_selectors(string: str, subs_list: list, stdscr, debug_line, prev_offset) -> list:
    matches = [MatchString(string[:], False)]
    #prev_offset = 0

    for p in subs_list:
        #last_substr = matches[-1].content

        ## all patterns must match
        ## return None if one does not match
        #if p not in last_substr:
        #    return None

        #if DEBUG:
        #    stdscr.addstr(20+i, prev_offset, last_substr)
        #    prev_offset += 1 + len(last_substr)

        #ind = last_substr.index(p)
        #pre, post = last_substr[:ind], last_substr[ind+len(p):]
        #matches = matches[:-1] + [MatchString(pre, False)] + [MatchString(p, True)] + [MatchString(post, False)]

        selector = dispatch_selectors(p)
        if selector is None: continue

        match_res = selector(matches, stdscr, prev_offset, debug_line)
        if match_res is None: return # every selector must match
        matches = match_res
        prev_offset += 20 + len(matches[-1].content)

    ## if no matches were found, return None?
    #if len(matches) == 1 and not matches[0].ismatch:
    #    return None

    return matches

'''
what it must return is
[
([list of keys leading to] {currently parsed options})
]
the list of keys can be made of MatchStrings
but it's better to encapsulate the [MatchString]-list pattern
'''
def match_child_data(substr, lambda_for_key_val, opts: dict, accum_res: list) -> list:
    #print(f'{opts} ->')

    if not isinstance(opts, dict):
        # no "child" to match anything
        return accum_res

    # the current options match
    #if any(lambda_for_key_val(name, val) for name, val in opts.items()):
    #a_match = next(((name, val) for name, val in opts.items() if lambda_for_key_val(name, val)), None)
    a_match = lambda_for_key_val(substr, opts)
    if a_match is not None:
        #return [OptionPath([str(opts.items())], opts)]
        #return [OptionPath(['DEBUG'], opts)]
        # TODO: highlight the matched option?
        name, val = a_match
        # substitute this in opts... it will mutate the dictionary inplace...
        ret_opts = {} # make deep copy, preserve the order of opt, insert
        for k, v in opts.items():
            if k == str(name): # or str(v) == str(val):
                # insert the matched string with the match result
                # i.e. it turns the original opts content into MatchStringL
                ret_opts[name] = val
            else:
                #ret_opts[str(k) + f'{type(name)}-{type(val)}'] = v
                ret_opts[k] = v
        #return accum_res + [OptionPath([f'|{k} {name} {k == str(name)}|'], ret_opts)]
        return accum_res + [OptionPath([], ret_opts)]

    # if not in the current level -- nest
    matched_opt_paths = []
    for k, val in opts.items():
        if isinstance(val, dict):
            deep_match_paths = match_child_data(substr, lambda_for_key_val, val, accum_res)
            for deep_match in deep_match_paths:
                opt_path = [k] + deep_match.path
                matched_opt_paths.append(OptionPath(opt_path, deep_match.options))

    #print(f'{opts} -> {matched_opt_paths}')
    return matched_opt_paths

def match_opt_names(substr, opts):
    # i.e. None cannot be in the keys!
    a_match = next((name for name in opts.keys() if substr in str(name)), None)
    if a_match is None:
        return None
    return MatchStringL(a_match, True), opts[a_match]

def match_only_leafs(substr, node_value):
    return not isinstance(node_value, dict) and substr in str(node_value)

def match_opt_values(substr, opts):
    a_match = next(((key, val) for key, val in opts.items() if match_only_leafs(substr, val)), None)
    if a_match is None:
        return None
    key, match_val = a_match
    # return the whole new pair, with the match highlighted
    #ret = key, MatchStringL(str(match_val) + 'HEY', True)
    ret = key, MatchStringL(str(match_val), True)
    return ret
    #return key, MatchStringL(str(match_val) + f'HEY {ret[1].match_strings}', True)

# def match_child_name(substr: str, opts: dict) -> list:
#     # should I test whether "name" is str or int?
#     # the user can supply a dict or list or set in there
#     return match_child_data(lambda op: (any(substr in str(k) for k in opts.keys()), name), opts)
# def match_child_val(substr: str, opts: dict) -> list:
#     # the "value" is only the leave of this dict-based tree
#     return match_child_data(lambda n, val: match_only_leafs(substr, val), opts)

def match_substr(substr: str, opts: dict) -> list:
    '''match_substr(substr: str, opts: dict) -> list

    return [OptionPath]
    '''

    if not isinstance(opts, dict):
        return []

    matched_paths = []
    for k, v in opts.items():
        name = str(k)

        # match case-insensitive
        if substr.upper() in name.upper():
            # a match!
            ind = name.upper().find(substr.upper())
            pre = name[:ind]
            mch = name[ind:ind+len(substr)]
            pos = name[ind+len(substr):]
            mstring = MatchStringL([MatchString(pre, False), MatchString(mch, True), MatchString(pos, False)])

            # narrowed the path nesting
            matched_paths.append(OptionPath([mstring], v))
            #next_matched_opts.append(OptionPath(next_opt_paths, v))

        elif isinstance(v, dict):
            for deep_path, remaining_opts in match_substr(substr, v):
                matched_paths.append(OptionPath([name] + deep_path, remaining_opts))

    return matched_paths


def match_options_to_selectors(opt_paths: list, patterns: list, stdscr) -> list:
    '''match_options_to_selectors(opt_paths: list(OptionPath), patterns: list, stdscr) -> list

    Now opts is a nested dictionary. It is a DataPoints structure:
    the leafs of the tree are the values of DP variables.
    The matching to patterns goes recursively, to test each full DP name.
    Patterns can be either any string that is matched to a DP name,
    or they begin with `.` then the DP value is matched to type,
    or `>` then the child of DP is matched and the search continues from parent,
    or `=` then the child value is matched and the search continues from parent.

    Ok, the meaning of `>` is different now? It matches the child name
    but keeps the search in the current DP node.
    Previously, it looked for the child name under the last matched DP node.
    Now these 3 operators act the same relative way.
    '''

    # if the patterns are exhausted, convert the search into a flat list of match strings?
    if not patterns:
        flat_opts = []
        for path, opts in opt_paths:
            if not isinstance(opts, dict):
                # TODO: just return a list of match strings and convert it to full strings when needed
                #mstring = MatchString('.'.join(path + [str(i) for i in p]) + '=' + str(opts), False)
                flat_option = path, opts if isinstance(opts, MatchStringL) else MatchStringL(f'{opts}')
                flat_opts.append(flat_option)
                continue

            for p, v in iteritems_recursive(opts):
              #flat_opts.append(DataPoint('.'.join([str(i) for i in p]), v))
              # I cannot return just DataPoint!
              # I need to return MatchString
              #mstring = MatchString('.'.join(path + [str(i) for i in p]) + '=' + str(v), False)
              #flat_opts.append(mstring)
              #print(path, p, v)
              #flat_option = path + [i if isinstance(i, MatchStringL) else MatchStringL(i) for i in p] + [MatchStringL(f'={v}')]
              flat_path = path + [i if isinstance(i, MatchStringL) else MatchStringL(str(i)) for i in p]
              val = v if isinstance(v, MatchStringL) else MatchStringL(f'{v}')
              flat_opts.append((flat_path, val))

        return flat_opts

    # no options left, but patterns are still there
    if not opt_paths: return []

    # the current pattern to match
    pm = patterns[0]
    assert len(pm)>0

    # TODO: not clear how to return match strings for child/sibling matches
    #       i.e. what goes to the action manu then?
    if pm[0] in ('>', '='):
        if len(pm)==1:
            # incomplete pattern definition - skip it
            return match_options_to_selectors(opt_paths, patterns[1:], stdscr)

        # search for a child with name match
        tomatch = pm[1:]
        #mstring, matched_opts = match_child_name(tomatch, opts)

        next_opt_paths = [] #[OptionPath([tomatch], opt_paths[0].options)]
        for path, opts in opt_paths:
            accum_res = [] # the child search has to deepcopy the options
            if   pm[0] == '>':
                #matched_opts = match_child_name(tomatch, opts)
                matched_opts = match_child_data(tomatch, match_opt_names, opts, accum_res)
            elif pm[0] == '=':
                #matched_opts = match_child_val(tomatch, opts)
                matched_opts = match_child_data(tomatch, match_opt_values, opts, accum_res)

            for op in matched_opts:
                next_opt_paths.append(OptionPath(path + op.path, op.options))

        # launch the rest of search
        return match_options_to_selectors(next_opt_paths, patterns[1:], stdscr)

    #elif pm[0] == '.':
    #    # search for child with _value_ of the given type
    #    mstring, matched_opts = match_type(pm[1:], opts)
    #    rest = match_options_to_selectors(matched_opts, patterns[1:], stdscr)
    #    yield [mstring + r for r in rest]

    #elif pm[0] == '=':

    else: # search fields names
        next_matched_opts = []
        for path, op_tree in opt_paths:
            if not isinstance(op_tree, dict):
                # no name to match
                continue

            for deep_path, remaining_opt in match_substr(pm, op_tree):
                next_matched_opts.append(OptionPath(path+deep_path, remaining_opt))

        return match_options_to_selectors(next_matched_opts, patterns[1:], stdscr)

#    for k, v in opts.items():
#        if isinstance(v, dict):
#          for k1,v1 in iteritems_recursive(v):
#            yield (k,)+k1, v1
#        else:
#          yield (k,),v

#def iteritems_recursive(d):
#    for k,v in d.items():
#      if isinstance(v, dict):
#        for k1,v1 in iteritems_recursive(v):
#          yield (k,)+k1, v1
#      else:
#        yield (k,),v

def _comline_remove_last_word(comline_cur, comline):
    # damn
    if comline_cur==0:
        return None

    #
    starting_cur = comline_cur
    # move the white space
    cur_char = comline[comline_cur-1]
    while cur_char.isspace() and comline_cur>0:
        comline_cur -= 1
        cur_char = comline[comline_cur-1]

    if comline_cur==0:
        new_comline = comline[starting_cur:]
        return new_comline, comline_cur

    while not cur_char.isspace() and comline_cur>0:
        comline_cur -= 1
        cur_char = comline[comline_cur-1]

    new_comline = comline[:comline_cur] + comline[starting_cur:]

    return new_comline, comline_cur

class Comline:
    def __init__(self, prompt='> '):
        self.comline = ""
        self.cur_pos = 0
        self.prompt  = prompt
        self.cur_line = 0 # the line where the comline was printed the last time

    def __repr__(self):
        return f'Comline(prompt={self.prompt})'
    def __str__(self):
        return f'{self.comline}'
    def __len__(self):
        return len(self.comline)
    def split(self):
        return self.comline.split()
    def remove_last_word(self):
        res = _comline_remove_last_word(self.cur_pos, self.comline)
        if res:
            self.comline, self.cur_pos = res

    def set_cursor(self, stdscr):
        #comline.set_cursor()
        stdscr.move(self.cur_line, len(self.prompt) + self.cur_pos)

    def print_to_scr(self, stdscr, cur_line, debug=False):
        n_lines_printed = 0
        stdscr.addstr(cur_line, 0, f'{self.prompt}{self.comline}')
        self.cur_line = cur_line
        n_lines_printed += 1

        if debug:
            #n_lines_printed += print_comline_info(stdscr, cur_line+1)
            stdscr.addstr(cur_line+1, 0, ' '*(len(self.prompt) + self.cur_pos) + "^")
            #stdscr.refresh()

            stdscr.addstr(cur_line+2, 0, f'user cur: {self.cur_pos} {len(self.comline)}')

            n_lines_printed += 2

        return n_lines_printed

    def backspace(self):
        if self.cur_pos>0:
          self.comline = self.comline[:self.cur_pos-1] + self.comline[self.cur_pos:]
          self.cur_pos -= 1

    def insert(self, k):
        assert k.isprintable()
        self.comline = self.comline[:self.cur_pos] + k + self.comline[self.cur_pos:] # chr(k)
        self.cur_pos += 1

    def moveto_end(self):
        self.cur_pos = len(self.comline)
    def moveto_home(self):
        self.cur_pos = 0
    def moveto_left(self):
        self.cur_pos -= 1 if self.cur_pos>0 else 0
    def moveto_right(self):
        self.cur_pos += 1 if self.cur_pos<len(self.comline) else 0

    def moveto_right_word(self):
        if self.cur_pos == len(self.comline):
            return
        # last char -- move to the end
        elif self.cur_pos == len(self.comline)-1:
            self.cur_pos += 1
            return

        self.cur_pos += 1

        # pass white space
        cur_char = self.comline[self.cur_pos]
        while cur_char.isspace() and self.cur_pos<len(self.comline):
            self.cur_pos += 1
            if self.cur_pos == len(self.comline):
                break
            cur_char = self.comline[self.cur_pos]

        if self.cur_pos == len(self.comline):
            return

        # pass letters
        cur_char = self.comline[self.cur_pos]
        while not cur_char.isspace() and self.cur_pos<len(self.comline):
            self.cur_pos += 1
            if self.cur_pos == len(self.comline):
                break
            cur_char = self.comline[self.cur_pos]

        return

    def moveto_left_word(self):
        if self.cur_pos == 0:
            return

        # pass white space
        cur_char = self.comline[self.cur_pos-1]
        while cur_char.isspace() and self.cur_pos>0:
            self.cur_pos -= 1
            cur_char = self.comline[self.cur_pos-1]

        if self.cur_pos == 0:
            return

        # pass letters
        cur_char = self.comline[self.cur_pos-1]
        while not cur_char.isspace() and self.cur_pos>0:
            self.cur_pos -= 1
            cur_char = self.comline[self.cur_pos-1]

    def edit_key(self, k):
        if k in ("KEY_BACKSPACE", "\x7f"):
            #if comline_cur>0:
            #  comline = comline[:comline_cur-1] + comline[comline_cur:]
            #  comline_cur-=1
            self.backspace()

        elif ord(k[0]) == KEY_CTRLW: # remove the last word
            #res = comline_remove_last_word(comline_cur, comline)
            #if not res:
            #    continue
            #comline, comline_cur = res
            self.remove_last_word()

        elif ord(k[0]) == 0: # the null character
            pass

        elif k == "KEY_END":
            #comline_cur = len(self)
            self.moveto_end()
        elif k == "KEY_HOME":
            #comline_cur = 0
            self.moveto_home()

        # the keys that shouldn't affect the commandline
        elif k == "kRIT3": # alt-right
            pass
        elif k == "kLFT3": # alt-left
            pass

        elif k == "KEY_SRIGHT": # shift-right
            pass
        elif k == "KEY_SLEFT":  # shift-left
            pass

        elif k == "KEY_SF": # shift-down
            pass
        elif k == "KEY_SR": # shift-up
            pass

        elif k == "KEY_NPAGE": # page down
            pass
        elif k == "KEY_PPAGE": # page up
            pass

        elif k == "kUP3": # alt-up
            pass
        elif k == "kDN3": # alt-down
            pass

        elif k == "kRIT5": # ctrl-right
            self.moveto_right_word()

        elif k == "kLFT5": # ctrl-left
            self.moveto_left_word()

        # up-down control the selection among the matched options
        elif k == "KEY_UP":
            pass
        elif k == "KEY_DOWN":
            pass

        elif k == "KEY_LEFT":
            #comline_cur -= 1 if comline_cur>0 else 0
            self.moveto_left()
        elif k == "KEY_RIGHT":
            #comline_cur += 1 if comline_cur<len(self) else 0
            self.moveto_right()

        # if printable
        elif k.isprintable():
            #comline = comline[:comline_cur] + k + comline[comline_cur:] # chr(k)
            #comline_cur+=1
            self.insert(k)

        else:
            return False

        # if one of known keys
        return True

def main(action_menu=None):
  def curses_program(stdscr):
    #global comline, comline_cur
    comline = Comline(prompt='> ')

    __max_y, __max_x = stdscr.getmaxyx()

    curses.start_color()
    curses.use_default_colors()

    highligh_color = 30 # the blue-green use match color
    curses.init_pair(1, highligh_color, -1)

    #select_grey_bkg = 253 # the light-grey
    #curses.init_pair(2, select_grey_bkg, -1)

    styleMatchedText = curses.color_pair( 1 )
    #curses.init_pair(1,curses.COLOR_BLACK, curses.COLOR_CYAN)
    styleNormalText = curses.A_NORMAL
    styleSelectLine = curses.A_BOLD | curses.A_REVERSE # | curses.color_pair(2)

    stdscr.clear()

    k = " "
    cur_select_cursor = 0
    while True:
        stdscr.erase()

        cur_line = 0
        # print the UI for the user
        stdscr.addstr(cur_line, 0, f'UI info: ESC to exit, type to search & select, up-down-tab to cherry pick, ENTER to act on selection')
        cur_line += 1

        # print the command line
        cur_line += comline.print_to_scr(stdscr, cur_line, debug=DEBUG)
        #stdscr.addstr(cur_line, 0, f'{prompt}{comline}')
        #cur_line += 1
        #if DEBUG: cur_line += print_comline_info(stdscr, cur_line)

        if DEBUG:
            if ord(k[0]) != 0:
                stdscr.addstr(cur_line, 0, f'user char: {k} {len(k)} {ord(k[0])} {ord(k[0]) == KEY_ESC}')
            else:
                stdscr.addstr(cur_line, 0, f'user char: <null_character> {len(k)} {ord(k[0])} {ord(k[0]) == KEY_ESC}')
            cur_line += 1

        # act on the user input as a set of substrings to find
        patterns = comline.split()

        # seave through the substrings
        if patterns:
            #matched_opts = match_options_to_selectors(opts, patterns, stdscr)
            opts_to_match = deepcopy(opts)
            matched_opt_paths = match_options_to_selectors(opts_to_match, patterns, stdscr)
            #import pdb
            #pdb.set_trace()
            #matched_opts = flatten_opt_paths(matched_opt_paths)
            matched_opts = matched_opt_paths

            if DEBUG:
                 stdscr.addstr(cur_line+20, 0, f'matched opts {len(matched_opts)}')

            #for opt_num, (opt, val) in enumerate(opts):
            #    prev_offset = 0

            #    debug_line = opt_num
            #    matches = match_string_to_selectors(opt, patterns, stdscr, debug_line, prev_offset)
            #    if DEBUG:
            #        stdscr.addstr(cur_line+debug_line, prev_offset, opt)
            #        prev_offset += 3 + len(opt)

            #        #stdscr.addstr(cur_line+debug_line+20, prev_offset, f'{matches}')

            #    if matches: matched_opts.append((opt_num, matches))

        else:
            #matched_opts = [(i, [MatchString(o, False)]) for i, (o, v) in enumerate(opts)]
            matched_opts = flatten_opt_paths(opts)

        if cur_select_cursor >= len(matched_opts):
            cur_select_cursor = len(matched_opts) - 1
            # it will make the cursor negative when there are no matches

        if cur_select_cursor < 0 and len(matched_opts) > 0:
            cur_select_cursor = 0

        line_offset = cur_line
        #for matched_o_num, (opt_num, matched_o) in enumerate(matched_opts):
        for matched_o_num, (matched_o, val) in enumerate(matched_opts):
            # split into substrings
            if matched_o_num >= __max_y: # if it goes outside the screen
                break

            if matched_o_num == cur_select_cursor:
                select_prompt = '> '

            else:
                select_prompt = '  '

            line_opt = styleNormalText
            #if opt_num in selected_opts:
            #    line_opt = styleSelectLine

            # Print the matched options
            stdscr.addstr(line_offset+matched_o_num, 0, select_prompt)
            for i, substr in enumerate(matched_o):
                if i != 0:
                    stdscr.addstr(FIELD_SEPARATOR, line_opt | styleNormalText)

                if not isinstance(substr, MatchStringL):
                    #stdscr.addstr(str(substr) + "DEBUG!", line_opt | styleNormalText)
                    stdscr.addstr(str(substr), line_opt | styleNormalText)

                else:
                    #opt = line_opt | (styleMatchedText if substr.ismatch else styleNormalText)
                    #stdscr.addstr(substr.content, opt)
                    # def print_to_curses(self, stdscr, line_option, styleMatchedText, styleNormalText, coord=None):
                    #stdscr.addstr("WAT?!", line_opt | styleNormalText)
                    substr.print_to_curses(stdscr, line_opt, styleMatchedText, styleNormalText)

            # print the value leafs
            # check if they got matched
            if isinstance(val, MatchStringL):
                stdscr.addstr('=', line_opt | styleNormalText)
                val.print_to_curses(stdscr, line_opt, styleMatchedText, styleNormalText)

            else:
                stdscr.addstr(f'={val}', line_opt | styleNormalText)

        # Print selected options (debugging?)
        for i, sel_opt_num in enumerate(selected_opts):
            stdscr.addstr(cur_line+i, 0, opts[sel_opt_num])

        comline.set_cursor(stdscr)
        #stdscr.move(0, len(prompt) + comline.cur_pos)

        try:
            k = stdscr.getkey() # get character or timeout

        except curses.error as e:
            # capture the timeout
            if str(e) == "no input":
                continue
            else:
                raise e

        #cur.puts(f'user char: {k} type {type(k)} and ==^[ {k=="^["}')
        #cur.puts(f'user char: {k[0]} type {type(k[0])} and ==^ {k=="^"}')
        #cur.puts(f'user char: {len(k)}')
        #cur.puts(f'user char: {ord(k[0])}')
        #cur.puts(f'user char: {k.isprintable()}')
        stdscr.refresh()

        if ord(k[0]) == KEY_ESC:
            # Don't wait for another key
            # If it was Alt then curses has already sent the other key
            # otherwise -1 is sent (Escape)
            stdscr.nodelay(True)
            n = stdscr.getch()

            if n == -1:
                # Escape was pressed
                sys.exit(0)

            # Return to delay
            stdscr.nodelay(False)
            # run something on alt-<n>
            #cur.puts(f'user alt-char: {n}')

            # else it's an ALT
            if n == ord('w'):
                #stdscr.addstr(50, 0, "alt-w !")
                #res = comline_remove_last_word(comline_cur, comline)
                #if not res:
                #    continue
                #comline, comline_cur = res
                comline.remove_last_word()

        # up-down control the selection among the matched options
        elif k == "KEY_UP":
            if cur_select_cursor > 0:
                cur_select_cursor -= 1
        elif k == "KEY_DOWN":
            if cur_select_cursor < len(matched_opts) - 1:
                cur_select_cursor += 1

        # capture ENTER to select and deselect options?
        # ENTER is bad, because it is on the same side of keyboard
        # as the arrow keys -- the same hand types everything
        # there should be a large key button on the left hand!
        elif ord(k[0]) == 10 and len(matched_opts) > 0 and action_menu is not None:
            # launch the action menu
            if selected_opts:
                action_menu(stdscr, [opts[i] for i in selected_opts])

            else: # act on all matched
                opt_to_act = [opts[i] for i, _ in matched_opts]
                action_menu(stdscr, opt_to_act)

        # ok, just use TAB to move to the action on the selected options
        elif ord(k[0]) == 9 and len(matched_opts) > 0:
            opt_num, _ = matched_opts[cur_select_cursor]
            if opt_num in selected_opts:
                selected_opts.discard(opt_num)
            else:
                selected_opts.add(opt_num)

        # comline edit has to be the last
        # because of "printable" option:
        # comline edit inserts this into the comline string
        # but the above KEY_UP etc are also printable strings
        elif comline.edit_key(k):
            continue # if the comline knows how to processes this key

    #stdscr.addstr(cur_y, 0, 'Hello, curses!')

    #cur_y = 0
    #stdscr.addstr(cur_y, 0, 'Hello, curses!')
    #cur_y += 1
    #stdscr.addstr(cur_y, 0, 'Hello, curses!')

    c = stdscr.getch()

    stdscr.getch()
    stdscr.erase()

    #editwin = curses.newwin(5,30, 2,1)
    #rectangle(stdscr, 1,0, 1+5+1, 1+30+1)
    #stdscr.refresh()
    #box = Textbox(editwin)
    ## Let the user edit until Ctrl-G is struck.
    #box.edit()
    ## Get resulting contents
    #message = box.gather()
    #cur.puts(f'user message: {message}')

    # just pause it
    stdscr.getch()

  return curses_program

from time import time

def menu_action(action_polling, action_writing):
  def action(screen, options, timeout=1000):
    comline = Comline()

    screen.clear()
    screen.timeout(timeout) # time to wait for character

    prompt = "> "
    k = " "
    cur_select_cursor = 0
    action_writing_output = ""
    while True:
        screen.erase()

        screen.addstr(0, 0, f'UI info: ESC to go back, type and ENTER to write to all selected options, it reads every {timeout}ms')
        #screen.addstr(0, 0, f'{prompt}{comline}')
        comline.print_to_scr(screen, 1, debug=DEBUG)
        screen.addstr(2, 0, ' '*(len(prompt) + comline.cur_pos) + "^")
        screen.addstr(3, 0, 'just printing the selected options, and no action on ENTER')
        screen.addstr(4, 0, f'writing: {action_writing_output}')
        screen.addstr(5, 0, f'{time()}')

        #screen.move(0, len(prompt) + comline.cur_pos)
        comline.set_cursor(screen)

        action_polling(screen, options)

        # draw the screen and getkey
        screen.refresh()
        try:
            k = screen.getkey() # get character or timeout

        except curses.error as e:
            # capture the timeout
            if str(e) == "no input":
                k = '\0' # null character
                continue
            else:
                raise e

        # if ENTER - action_writing
        # else: ESC to go back
        #       or edit the comline

        if ord(k[0]) == KEY_ESC:
            # Don't wait for another key
            # If it was Alt then curses has already sent the other key
            # otherwise -1 is sent (Escape)
            screen.nodelay(True)
            n = screen.getch()

            if n == -1:
                # Escape was pressed
                return # go back

            # Return to delay
            screen.nodelay(False)
            # run something on alt-<n>
            #cur.puts(f'user alt-char: {n}')

            # else it's an ALT
            if n == ord('w'):
                #screen.addstr(50, 0, "alt-w !")
                #res = comline_remove_last_word(comline_cur, comline)
                #if not res:
                #    continue
                #comline, comline_cur = res
                comline.remove_last_word()

        # capture ENTER to select and deselect options?
        # ENTER is bad, because it is on the same side of keyboard
        # as the arrow keys -- the same hand types everything
        # there should be a large key button on the left hand!
        elif ord(k[0]) == 10:
            # launch the write action
            action_writing_output = action_writing(screen, options, str(comline))

        elif comline.edit_key(k):
            pass # if the comline knows how to processes this key

  return action

def action_view(screen, options, line_offset=20):
    for i, opt in enumerate(options):
        screen.addstr(line_offset+i, 0, str(opt))

def action_write(screen, options, comline_string):
   return f'NOT doing anything with {comline_string}'

if __name__ == "__main__":
    from sys import argv

    if '--demo' in argv:
        print('running the demo')

    else:
        import argparse
        parser = argparse.ArgumentParser(
            formatter_class = argparse.RawDescriptionHelpFormatter,
            description = "Demo the menu with --demo or browse an OPC-UA server via uasync",
            epilog = """Example:
   python3 curses_menu.py -u localhost:48010 -l0 -d 3 -n "ns=2;s=Can01"
   python3 curses_menu.py -u localhost:4841  -l0 -d 3 -n "ns=2;s=pp2"

Beware, uasync won't work on Python 3.6, it needs 3.9 or higher. Check python --version.
"""
        )

        # the asyncua example
        import asyncio
        from get_opcua_datapoints import _uals

        #opts = await _uals()
        opts = asyncio.run(_uals(parser))

    wrapper(main(menu_action(action_view, action_write)))


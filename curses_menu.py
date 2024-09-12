"""
https://wasimlorgat.com/posts/editor
https://hyperskill.org/blog/post/introduction-to-the-curses-library-in-python-text-based-interfaces
https://stackoverflow.com/questions/18551558/how-to-use-terminal-color-palette-with-curses
"""

import sys
import logging
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

from collections.abc import Mapping

class OptNode:
    def __init__(self, name, value=None, children=set(), parents=set(), logger=None):
        #super().__init__(*args) # not needed?
        self.name = str(name) # TODO: not sure if name is always str
        self.value = value
        self.children = children
        self.parents  = parents
        self.selected = False

        #
        for set_param in (self.children, self.parents):
            assert(isinstance(set_param, set))

            # check that all children are OptNode
            for item in set_param:
                assert isinstance(item, OptNode)

        self._highlight_name = 0, 0 # no highlight
        self._highlight_value = False

    def __hash__(self):
        return hash((self.name, self.value))

    def __repr__(self):
        return f'OptNode({repr(self.name)}, {repr(self.value)}, {repr(self.children)})'

    def __str__(self):
        if self.value is not None:
            return f'{self.name}={self.value}'

        else:
            return f'{self.name}'

    def highlight_name(self, start, end):
        assert start < end <= len(self.name)
        self._highlight_name = start, end

    def highlight_value(self, new_bool):
        # TODO: value is not necessarily a string, what if it is a dictionary?
        # let's just highlight all of it now
        self._highlight_value = new_bool

    def clear_highlights(self):
        self._highlight_name = 0, 0
        self._highlight_value = False
        #self.selected = False

        for c in self.children:
            c.clear_highlights()

    def print_to_menu(self, cursor, styleMatchedText, styleNormalText, coord=None):
        '''print_to_menu(self, cursor, coord=None)

        prints it to curses, with necessary highlights

        cursor -- the curses cursor
        coord = (line_num, char_pos) -- optional setting for cursor position
        '''

        if coord is not None:
            line_num, char_pos = coord
            cursor.move(line_num, char_pos)

        pre = self.name[:self._highlight_name[0]]
        highlight = self.name[self._highlight_name[0]:self._highlight_name[1]]
        post = self.name[self._highlight_name[1]:]

        cursor.addstr(pre, styleNormalText)
        cursor.addstr(highlight, styleMatchedText)
        cursor.addstr(post, styleNormalText)

        if self.value is not None:
            # print the value too
            # add =
            cursor.addstr('=', styleNormalText)
            # value
            to_highlight = styleMatchedText if self._highlight_value else styleNormalText
            cursor.addstr(str(self.value), to_highlight)

    def opt_list(self, prefix_list=[]):
        # case of a cycle in the graph
        if self in prefix_list:
            #yield prefix_self
            yield prefix_list + [self]

        else:
            prefix_self = prefix_list + [self]
            yield prefix_self

            for opt in [c.opt_list(prefix_self) for c in self.children]:
                yield from opt

    def print_flat(self, prefix=''):
        #prefix_self = prefix + str(self)
        #print(prefix_self)

        #for n in self.children:
        #    n.print_flat(prefix_self + '.')
        for opt in self.opt_list():
            print('.'.join(str(i) for i in opt))

    def match_name(self, substr):
        if substr not in self.name:
            return False

        match_ind = self.name.index(substr)
        self.highlight_name(match_ind, match_ind+len(substr))
        return True

    def match_selector(self, selector):
        '''match_selector(self, selector)

        Returns True or False. Matches the basic selectors:
        = for value
        . for basic type
        the rest is name match
        '''
        assert len(selector) > 0
        if selector[0] in ('=', '.'):
            assert len(selector) > 1

        if selector[0] == '=' and selector[1:] == str(self.value):
            self.highlight_value(True)
            return True

        if selector[0] == '.':
            type_matched = False
            type_matched |= selector[1:] == 'int' and type(self.value) == int
            type_matched |= selector[1:] == 'float' and type(self.value) == float
            type_matched |= selector[1:] == 'str' and type(self.value) == str
            return type_matched

        return self.match_name(selector)

    def match_selectors(self, selectors, prev_nodes=[]):
        '''match_selectors(self, selectors, prev_nodes=[]):

        In general, matching returns an option list from the tree of OptNode-s.
        Therefore `match_selector` returns True or False whether this node
        matched the selector, and sets the highlights in self node, and in the
        child nodes if needed.

        Special selectors:
        = for value
        . for basic types of value
        > prefix to match child nodes, including [.=]
        '''

        # test and clean up the selectors here
        checked_selectors = []
        for sel in selectors:
            assert len(sel) > 0

            if all(ch in ('>', '=', '.') for ch in sel):
                if logger is not None: # TODO: add a default logger
                    logger.warning(f'got an empty special selector: {sel}')
                continue

            checked_selectors.append(sel)

        # run the recursive matching
        if len(checked_selectors) == 0:
            # done
            for opt in self.opt_list():
                yield prev_nodes + opt

        else:
            yield from self._match_selectors(checked_selectors, prev_nodes)

    def _match_selectors(self, selectors, prev_nodes=[]):
        assert len(selectors) > 0
        #if len(selectors) == 0:
        #    # the all selectors got mathed
        #    for opt in self.opt_list():
        #        #yield prev_nodes + opt
        #        return prev_nodes + opt

        sel = selectors[0]
        assert len(sel) > 0

        ## skip empty special selectors
        ##if sel[0] in ('>', '=', '.') and len(sel) == 1:
        #if all(ch in ('>', '=', '.') for ch in sel):
        #    if logger is not None: # TODO: add a default logger
        #        logger.warning(f'got an empty special selector: {sel}')
        #    selectors = selectors[1:]
        #    sel = selectors[0]
        #    #self.match_selectors(selectors[1:], prev_nodes)

        matched = False
        matched_self = False
        if sel[0] == '>':
            # children names
            cnode_selector = sel[1:]

            for c in self.children:
                #yield from c.match_selectors([sel[0][1:]] + selectors[1:], prev_nodes + [self])
                matched |= c.match_selector(cnode_selector)

        else:
            matched = matched_self = self.match_selector(sel)

        next_selectors = selectors[1:] if matched else selectors
        if len(next_selectors) == 0:
            # done
            for opt in self.opt_list():
                yield prev_nodes + opt

        elif matched and not matched_self:
            # matched something in child nodes
            # the matching process stays at this node
            yield from self._match_selectors(next_selectors, prev_nodes)

        else:
            for c in self.children:
                yield from c._match_selectors(next_selectors, prev_nodes + [self])

def opt_tree(pydict, parent_nodes=set()):
    '''OptTree(pydict):

    Translation from a Python Mapping to a tree of `OptNode` option nodes.
    A node is a name, an optional value, and an optional mapping to child nodes.
    A Python mapping is translated into a set of nodes as:
    * a key that is a tuple becomes an OptNode and its value is an OptNode
    * a key that is not a tuple, with a non-dict value becomes a leaf OptNode
      i.e. with no child nodes
    * a key with value that is a mapping becomes an OptNode with no value
      but with children made out of the mapping
    '''

    if isinstance(pydict, OptNode):
        return set((pydict,))

    if isinstance(pydict, tuple):
        node_name, node_val = pydict
        return set((OptNode(node_name, node_val, children=set(), parents=parent_nodes),))

    if not isinstance(pydict, Mapping):
        # it is just one value
        # we save it as the node name
        return set((OptNode(pydict, value=None, children=set(), parents=parent_nodes),))

    # it is a Python mapping
    # i.e. a set of nodes
    nodes = set()
    for k, v in pydict.items():
        if isinstance(k, tuple):
            name, val = k
            nodes.add(OptNode(name, val, children=opt_tree(v), parents=parent_nodes))

        # leaf in the Python dict
        elif not isinstance(v, Mapping):
            nodes.add(OptNode(k, v, children=set(), parents=parent_nodes))

        else:
            nodes.add(OptNode(k, None, children=opt_tree(v), parents=parent_nodes))

    return nodes

# demo nested structure
some_nested_structure = {'some':
        {'nested': 2, 'struct': {'bar': 3, 'baz': 5}},
        'just': 5,
        'Just': 5,
        'foo': {
            'Bar': 77,
            'bar': {'foo': 88, 'ccc': {'qwe': 5, 'enable': True, 'bar': 18}, 'baz': 'work'},
            'qwe': {'ccc': {'qwe': 5, 'enable': True, 'bar': 18}, 'baz': 'work'},
            },
        'Foo': {72: 'Bar', 'bar': {'baz': 88}},
        'and_cases': {'foo': {'bar': 88}, 'baz': {'Bar': 55}},
        'more': {'nestings': 67, 5: 'five'},
        'and': 'only_string',
        'only_strings': {'foo': 'bar', 'baz': 'qwe',
            'plus': {'and': 'five', 'more': 'less'},
            'Connectivity': 'PPB1A'},
        }

# convert to OptNode
some_nested_structure_nodes = opt_tree(some_nested_structure)

# opts should be a flat options list

DEBUG = True

FIELD_SEPARATOR='.'

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

#
# it is also a graph, of programs now
class MenuProg:
    def __init__(self, next_prog=None):
        #self.comline_prog = comline_prog
        #self.poling_prog  = poling_prog
        # the options graph
        #self.opts = set()
        #self.next_prog  = next_prog
        #self.logger = logger

        self.cur_select_cursor = 0
        self.next_prog = next_prog

    def __call__(self, cscreen, opts_graph=set(), logger=None):
        logger.debug('MenuProg')

        # if no options, exit
        if not opts_graph:
            if logger is not None:
                logger.debug('MenuProg was called with no options')
            return

        comline = Comline(prompt='> ')

        styleMatchedText = curses.color_pair( 1 )
        #curses.init_pair(1,curses.COLOR_BLACK, curses.COLOR_CYAN)
        styleNormalText = curses.A_NORMAL
        styleSelectLine = curses.A_BOLD | curses.A_REVERSE # | curses.color_pair(2)

        cscreen.clear()
        while True:
            cscreen.erase()
            # comline program?
            # process the input and print the comline?
            # the comline returns processes the input and returns itself
            # the polling prog does whatever with the:
            # screen, comline, and options -- and returns selected options? or more?
            # the action prog does something on the selected options and the rest
            # action program is a nested MenuProg
            # clear the previous highlights:
            for n in opts_graph:
                n.clear_highlights()

            ## act on the user input as a set of substrings to find
            #patterns = comline.split()
            logger.debug('MenuProg: poll iteration')

            # the set of selected option lists
            selected_opts = set()

            # TODO: global implicit expected styling: pair 1
            styleMatchedText = curses.color_pair( 1 )
            #curses.init_pair(1,curses.COLOR_BLACK, curses.COLOR_CYAN)
            styleNormalText = curses.A_NORMAL
            styleSelectLine = curses.A_BOLD | curses.A_REVERSE # | curses.color_pair(2)

            __max_y, __max_x = cscreen.getmaxyx()

            k = " "
            #cur_select_cursor = 0

            cur_line = 0
            # print the UI for the user
            cscreen.addstr(cur_line, 0, f'UI info: ESC to exit, type to search & select, up-down-tab to cherry pick, ENTER to act on selection')
            cur_line += 1

            # print the command line
            cur_line += comline.print_to_scr(cscreen, cur_line, debug=DEBUG)

            if DEBUG:
                logger.debug(f'{cur_line:2} 0 user char: {k} {len(k)} {ord(k[0])} {ord(k[0]) == KEY_ESC}')

                if ord(k[0]) != 0:
                    cscreen.addstr(cur_line, 0, f'user char: {k} {len(k)} {ord(k[0])} {ord(k[0]) == KEY_ESC}')
                else:
                    cscreen.addstr(cur_line, 0, f'user char: <null_character> {len(k)} {ord(k[0])} {ord(k[0]) == KEY_ESC}')
                cur_line += 1

            # act on the user input as a set of substrings to find
            patterns = comline.split()

            # seave through the substrings
            if patterns:
                matched_opt_paths = []
                for n in opts_graph:
                    for opt in n.match_selectors(patterns):
                        matched_opt_paths.append(opt)

                matched_opts = matched_opt_paths
                logger.debug(f'matched opts {len(matched_opts)}')

            else:
                #matched_opts = opts_graph
                # just return all possible options
                # flat list of option lists
                matched_opts = []
                for node in opts_graph:
                    matched_opts += list(node.opt_list())

            if self.cur_select_cursor >= len(matched_opts):
                self.cur_select_cursor = len(matched_opts) - 1
                # it will make the cursor negative when there are no matches

            if self.cur_select_cursor < 0 and len(matched_opts) > 0:
                self.cur_select_cursor = 0

            line_offset = cur_line
            for matched_o_num, matched_opt_list in enumerate(matched_opts):
                # split into substrings
                if matched_o_num >= __max_y: # if it goes outside the screen
                    break

                if matched_o_num == self.cur_select_cursor:
                    select_prompt = '> '

                else:
                    select_prompt = '  '

                # TODO: add the selected options
                line_opt = styleNormalText
                #if opt_num in selected_opts:
                #    line_opt = styleSelectLine

                # Print the matched options
                cscreen.addstr(line_offset+matched_o_num, 0, select_prompt)

                for i, opt in enumerate(matched_opt_list):
                    if i != 0:
                        cscreen.addstr(FIELD_SEPARATOR, line_opt | styleNormalText)
                    opt.print_to_menu(cscreen, styleMatchedText, styleNormalText)

            # Print selected options (debugging?)
            for i, sel_opt_num in enumerate(selected_opts):
                cscreen.addstr(cur_line+i, 0, opts[sel_opt_num])

            comline.set_cursor(cscreen)
            #screen.move(0, len(prompt) + comline.cur_pos)

            try:
                k = cscreen.getkey() # get character or timeout

            except curses.error as e:
                # capture the timeout
                if str(e) == "no input":
                    return
                else:
                    raise e

            cscreen.refresh()

            if ord(k[0]) == KEY_ESC:
                # Don't wait for another key
                # If it was Alt then curses has already sent the other key
                # otherwise -1 is sent (Escape)
                cscreen.nodelay(True)
                n = cscreen.getch()

                if n == -1:
                    # Escape was pressed
                    #sys.exit(0)
                    break

                # Return to delay
                cscreen.nodelay(False)
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

            # up-down control the selection among the matched options
            elif k == "KEY_UP":
                if self.cur_select_cursor > 0:
                    self.cur_select_cursor -= 1
            elif k == "KEY_DOWN":
                if self.cur_select_cursor < len(matched_opts) - 1:
                    self.cur_select_cursor += 1

            # capture ENTER to select and deselect options?
            # ENTER is bad, because it is on the same side of keyboard
            # as the arrow keys -- the same hand types everything
            # there should be a large key button on the left hand!
            elif ord(k[0]) == 10 and len(matched_opts) > 0 and self.next_prog is not None:
                logger.debug(f'{cur_line:2} key ENTER passed: matched_opts={matched_opts} next_prog={self.next_prog}')

                #if next_prog:
                #    next_prog(cscreen, opts, next_prog, logger)
                #    # it processes the user keys
                #    # draws to the screen
                #    # loads the comline
                #    # what if the input is ENTER?
                #    # -- it is supposed to call it?
                #    # then why return selected options at all?

                # launch the action menu
                if selected_opts:
                    #action_prog(screen, [opts[i] for i in selected_opts])
                    self.next_prog(cscreen, [opts[i] for i in selected_opts], logger)

                else: # act on all matched
                    #opt_to_act = [opts[i] for i, _ in matched_opts]
                    #action_prog(screen, [opts[i] for i in matched_opts])
                    self.next_prog(cscreen, [i for i in matched_opts], logger)

            # ok, just use TAB to move to the action on the selected options
            elif ord(k[0]) == 9 and len(matched_opts) > 0:
                logger.debug(f'{cur_line:2} key TAB passed: matched_opts={matched_opts} cur_select_cursor={self.cur_select_cursor}')

                opt_num, _ = matched_opts[self.cur_select_cursor]
                if opt_num in selected_opts:
                    selected_opts.discard(opt_num)
                else:
                    selected_opts.add(opt_num)

            # comline edit has to be the last
            # because of "printable" option:
            # comline edit inserts this into the comline string
            # but the above KEY_UP etc are also printable strings
            elif comline.edit_key(k):
                pass # if the comline knows how to processes this key


            #c = cscreen.getch()
            #cscreen.getch()
            #cscreen.erase()

            # just pause it
            logger.debug('MenuProg: iteration pause')
            #cscreen.getch()

class StdMonitor:
    def __init__(self, next_prog=None):
        self.next_prog = next_prog

    def __call__(self, cscreen, opts_graph=set(), logger=None):
        logger.debug('StdMonitor')

        # if no options, exit
        if not opts_graph:
            if logger is not None:
                logger.debug('StdMonitor was called with no options')
            return

        comline = Comline(prompt='> ')

        styleMatchedText = curses.color_pair( 1 )
        #curses.init_pair(1,curses.COLOR_BLACK, curses.COLOR_CYAN)
        styleNormalText = curses.A_NORMAL
        styleSelectLine = curses.A_BOLD | curses.A_REVERSE # | curses.color_pair(2)

        cscreen.clear()
        while True:
            logger.debug('StdMonitor: poll iteration')
            cscreen.erase()

            for n in opts_graph:
                n.clear_highlights()

            cscreen.addstr(0, 0, f'UI info: ESC to go back, type and ENTER to write to all selected options, it reads every {timeout}ms')
            #cscreen.addstr(0, 0, f'{prompt}{comline}')
            comline.print_to_scr(cscreen, 1, debug=DEBUG)
            cscreen.addstr(2, 0, ' '*(len(prompt) + comline.cur_pos) + "^")
            cscreen.addstr(3, 0, 'just printing the selected options, and no action on ENTER')
            cscreen.addstr(4, 0, f'writing: {action_writing_output}')
            cscreen.addstr(5, 0, f'{time()}')
            cscreen.addstr(6, 0, f'{len(options)}')

            #cscreen.move(0, len(prompt) + comline.cur_pos)
            comline.set_cursor(cscreen)

            action_polling(cscreen, options)

            # draw the cscreen and getkey
            cscreen.refresh()
            try:
                k = cscreen.getkey() # get character or timeout

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
                cscreen.nodelay(True)
                n = cscreen.getch()

                if n == -1:
                    # Escape was pressed
                    return # go back

                # Return to delay
                cscreen.nodelay(False)
                # run something on alt-<n>
                #cur.puts(f'user alt-char: {n}')

                # else it's an ALT
                if n == ord('w'):
                    #cscreen.addstr(50, 0, "alt-w !")
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
                action_writing_output = action_writing(cscreen, options, str(comline))

            elif comline.edit_key(k):
                pass # if the comline knows how to processes this key

def action_view(screen, options, line_offset=20):
    #for i, opt in enumerate(options):
    #    screen.addstr(line_offset+i, 0, str(opt))
    styleNormalText = curses.A_NORMAL
    line_opt = styleNormalText

    for i, opt_list in enumerate(options):
        #opt.print_to_menu(screen, styleMatchedText, styleNormalText)
        #opt.print_to_menu(screen, styleNormalText, styleNormalText, (line_offset, 0))

        for opt_i, opt in enumerate(opt_list):
            if opt_i != 0:
                screen.addstr(FIELD_SEPARATOR, line_opt | styleNormalText)
                opt.print_to_menu(screen, styleNormalText, styleNormalText)

            else:
                opt.print_to_menu(screen, styleNormalText, styleNormalText, (line_offset+i, 0))


        pass

def main(action_menu=None, logger=None):
  if logger is None:
      logger = logging.getLogger(__file__)
      hdlr = logging.FileHandler(__file__ + ".log")
      logger.addHandler(hdlr)
      logger.setLevel(logging.DEBUG)

  # flat list of option lists
  opts = []
  for node in some_nested_structure_nodes:
      opts += list(node.opt_list())

  # the set of selected option lists
  selected_opts = set()

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

        if DEBUG:
            logger.debug(f'{cur_line:2} 0 user char: {k} {len(k)} {ord(k[0])} {ord(k[0]) == KEY_ESC}')

            if ord(k[0]) != 0:
                stdscr.addstr(cur_line, 0, f'user char: {k} {len(k)} {ord(k[0])} {ord(k[0]) == KEY_ESC}')
            else:
                stdscr.addstr(cur_line, 0, f'user char: <null_character> {len(k)} {ord(k[0])} {ord(k[0]) == KEY_ESC}')
            cur_line += 1

        # clear the previous highlights:
        for n in some_nested_structure_nodes:
            n.clear_highlights()

        # act on the user input as a set of substrings to find
        patterns = comline.split()

        # seave through the substrings
        if patterns:
            matched_opt_paths = []
            for n in some_nested_structure_nodes:
                for opt in n.match_selectors(patterns):
                    matched_opt_paths.append(opt)

            matched_opts = matched_opt_paths

            if DEBUG:
                 stdscr.addstr(cur_line+20, 0, f'matched opts {len(matched_opts)}')

        else:
            matched_opts = opts

        if cur_select_cursor >= len(matched_opts):
            cur_select_cursor = len(matched_opts) - 1
            # it will make the cursor negative when there are no matches

        if cur_select_cursor < 0 and len(matched_opts) > 0:
            cur_select_cursor = 0

        line_offset = cur_line
        for matched_o_num, matched_opt_list in enumerate(matched_opts):
            # split into substrings
            if matched_o_num >= __max_y: # if it goes outside the screen
                break

            if matched_o_num == cur_select_cursor:
                select_prompt = '> '

            else:
                select_prompt = '  '

            # TODO: add the selected options
            line_opt = styleNormalText
            #if opt_num in selected_opts:
            #    line_opt = styleSelectLine

            # Print the matched options
            stdscr.addstr(line_offset+matched_o_num, 0, select_prompt)

            for i, opt in enumerate(matched_opt_list):
                if i != 0:
                    stdscr.addstr(FIELD_SEPARATOR, line_opt | styleNormalText)
                opt.print_to_menu(stdscr, styleMatchedText, styleNormalText)

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
            logger.debug(f'{cur_line:2} key ENTER passed: matched_opts={matched_opts} action_menu={action_menu}')

            # launch the action menu
            if selected_opts:
                action_menu(stdscr, [opts[i] for i in selected_opts])

            else: # act on all matched
                #opt_to_act = [opts[i] for i, _ in matched_opts]
                #action_menu(stdscr, [opts[i] for i in matched_opts])
                action_menu(stdscr, [i for i in matched_opts])

        # ok, just use TAB to move to the action on the selected options
        elif ord(k[0]) == 9 and len(matched_opts) > 0:
            logger.debug(f'{cur_line:2} key TAB passed: matched_opts={matched_opts} cur_select_cursor={cur_select_cursor}')

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

    c = stdscr.getch()

    stdscr.getch()
    stdscr.erase()

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
        screen.addstr(6, 0, f'{len(options)}')

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
    #for i, opt in enumerate(options):
    #    screen.addstr(line_offset+i, 0, str(opt))
    styleNormalText = curses.A_NORMAL
    line_opt = styleNormalText

    for i, opt_list in enumerate(options):
        #opt.print_to_menu(screen, styleMatchedText, styleNormalText)
        #opt.print_to_menu(screen, styleNormalText, styleNormalText, (line_offset, 0))

        for opt_i, opt in enumerate(opt_list):
            if opt_i != 0:
                screen.addstr(FIELD_SEPARATOR, line_opt | styleNormalText)
                opt.print_to_menu(screen, styleNormalText, styleNormalText)

            else:
                opt.print_to_menu(screen, styleNormalText, styleNormalText, (line_offset+i, 0))

def action_write(screen, options, comline_string):
   return f'NOT doing anything with {comline_string}'

def curses_setup(logger=None):
    def curses_prog(curses_screen):
        curses.start_color()
        curses.use_default_colors()

        highligh_color = 30 # the blue-green use match color
        curses.init_pair(1, highligh_color, -1)

        #s = StdMainMenu()
        #m = MenuProg(s, None, logger)
        #m.opts = some_nested_structure_nodes
        #m(curses_screen)

        #
        m = MenuProg(StdMonitor())
        m(curses_screen, some_nested_structure_nodes, logger)

    return curses_prog

if __name__ == "__main__":
    from sys import argv
    logger = logging.getLogger(__file__)
    hdlr = logging.FileHandler(__file__ + ".log")
    logger.addHandler(hdlr)
    logger.setLevel(logging.DEBUG)

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

    #wrapper(main(menu_action(action_view, action_write)))
    wrapper(curses_setup(logger))


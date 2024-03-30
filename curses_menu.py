"""
https://hyperskill.org/blog/post/introduction-to-the-curses-library-in-python-text-based-interfaces
"""

import sys
import re

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

opts = 'klasd qwe pod 34 kjnd temp pre foo fuz toopoomoobooo'.split()

def iteritems_recursive(d):
    for k,v in d.items():
      if isinstance(v, dict):
        for k1,v1 in iteritems_recursive(v):
          yield (k,)+k1, v1
      else:
        yield (k,),v

some_nested_structure = {'some':
        {'nested': 2, 'struct': {3: 'bar', 'baz': 5}},
        'foo': 5,
        'more': {'nestings': 67, 5: 'five'},
        'and': 'only_string',
        'only_strings': {'foo': 'bar', 'baz': 'qwe'}
        }

opts = []
for p,v in iteritems_recursive(some_nested_structure):
    #print(f'{p} -> {v}')
    opts.append('.'.join([str(i) for i in p]) + '.' + str(v))

class Curs:
    def __init__(self, scr, init_x=0, init_y=0):
        self.__scr = scr
        self.__x = init_x
        self.__y = init_y
        self.__max_y, self.__max_x = scr.getmaxyx()

    def puts(self, string, newline=True):
        self.__scr.addstr(self.__y, self.__x, string)
        if newline:
            self.__y += 1
        self.__scr.refresh()

    def commandline(self, inp_processor=None, prompt="> "):
        self.__scr.addstr(self.__y, self.__x, prompt)
        editwin = curses.newwin(1, self.__max_x, self.__y, self.__x+len(prompt))
        self.__scr.refresh()
        box = Textbox(editwin)

        if inp_processor:
            validator = inp_processor(box)
            box.edit(validator)
        else:
            box.edit()
        message = box.gather()

        self.__y += 1
        self.puts(f'user message: {message}')
        return message

    def current_input_validator(self, box):
        cur_inp = box.gather()
        self.__y += 1
        self.puts(f'cur input: {cur_inp}', newline=False)
        self.__y -= 1
        return lambda char: None

comline = ""
comline_cur = 0
prompt  = "> "

from collections import namedtuple
MatchString = namedtuple("MatchString", 'content ismatch')

DEBUG=True

def match_string_to_substr_selector(cur_matches: list, substr: str, stdscr, prev_offset, debug_line) -> list:
    # the string matcher works on the current reminder
    last_substr = cur_matches[-1].content

    if substr not in last_substr:
        return None

    if DEBUG:
        stdscr.addstr(20+debug_line, prev_offset, last_substr)
        prev_offset += 1 + len(last_substr)

    ind = last_substr.index(substr)
    pre, post = last_substr[:ind], last_substr[ind+len(substr):]
    matches = cur_matches[:-1] + [MatchString(pre, False)] + [MatchString(substr, True)] + [MatchString(post, False)]

    return matches

basic_type_keywords = {
        'int': lambda s: s.isnumeric()
        }

def match_string_field_to_basic_type(cur_matches: list, selector_keyword: str, stdscr, prev_offset, debug_line) -> list:

    selector = basic_type_keywords.get(selector_keyword[1:])
    if not selector:
        return match_string_to_substr_selector(cur_matches, selector_keyword, stdscr, prev_offset, debug_line)

    # else match the string fields
    # a "field" is a .-separated part in the string
    # for simplicity let's start from the next "complete field"
    # i.e. the one that was not touched by the previous selectors
    last_substr = cur_matches[-1].content
    if len(cur_matches)>1 and cur_matches[-2].content[-1] != '.':
        # then the selector matching stopped in the middle of a field
        cutoff, *fields = last_substr.split('.')

    else:
        fields = last_substr.split('.')
        cutoff = None

    # find the first one that matches
    #if any(selector(f) for f in fields)
    matched_field_i = None
    for i, f in enumerate(fields):
        if selector(f):
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
        pre = '.'.join([cutoff] + fields[:matched_field_i])
    else:
        pre = '.'.join(fields[:matched_field_i])

    post = '.'.join(fields[matched_field_i+1:])
    if post: # if not empty
        post = '.' + post

    new_matches.append(MatchString(pre + '.', False))
    new_matches.append(MatchString(match_field, True))
    new_matches.append(MatchString(post, False))

    return cur_matches[:-1] + new_matches

def dispatch_selectors(selector_string: str):
    
    if selector_string[0] == '.':
        return match_string_field_to_basic_type

    return match_string_to_substr_selector

def match_string_to_selectors(string: str, subs_list: list, stdscr, i) -> list:
    matches = [MatchString(string[:], False)]
    prev_offset = 0
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

        match_res = selector(matches, p, stdscr, prev_offset, i)
        if match_res is None: return # every selector must match
        matches = match_res
        prev_offset += 20 + len(matches[-1].content)

    ## if no matches were found, return None?
    #if len(matches) == 1 and not matches[0].ismatch:
    #    return None

    return matches

def main(stdscr):
    global comline, comline_cur

    curses.start_color()
    curses.use_default_colors()
    highligh_color = 30
    curses.init_pair(1, highligh_color, -1)
    highlightText = curses.color_pair( 1 )
    #curses.init_pair(1,curses.COLOR_BLACK, curses.COLOR_CYAN)
    normalText = curses.A_NORMAL

    stdscr.clear()
    cur = Curs(stdscr)

    k = " "
    while True:
        stdscr.erase()

        stdscr.addstr(0, 0, prompt + comline)
        stdscr.addstr(1, 0, comline)
        stdscr.addstr(2, 0, ' '*comline_cur + "^")
        #stdscr.refresh()

        stdscr.addstr(4, 0, f'user cur: {comline_cur} {len(comline)}')
        stdscr.addstr(5, 0, f'user char: {k} {len(k)} {ord(k[0])}')

        # act on the user input as a set of substrings to find
        patterns = comline.split()

        matched_opts = [[MatchString(o, False)] for o in opts]
        # seave throush the substrings
        if patterns:
            #re_pattern = '.*' + '.*'.join(patterns) + '.*'
            #stdscr.addstr(7, 0, f're: {re_pattern}')
            #matched_opts = [o for o in opts if re.match(re_pattern, o)]
            #matched_opts = [o for o in matched_opts if substr in o]
            # simply:
            matched_opts = []
            for i, opt in enumerate(opts):
                matches = match_string_to_selectors(opt, patterns, stdscr, i)
                if matches: matched_opts.append(matches)

        cur_line = 8
        for matched_o in matched_opts:
            # split into substrings
            stdscr.addstr(cur_line, 0, f'user match: for ')
            for substr in matched_o:
                stdscr.addstr(substr.content, highlightText if substr.ismatch else normalText)
            cur_line += 1

        stdscr.move(0, len(prompt) + comline_cur)

        k = stdscr.getkey()
        #k = stdscr.getch()

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

        if k in ("KEY_BACKSPACE", "\x7f"):
            if comline_cur>0:
              comline = comline[:comline_cur-1] + comline[comline_cur:]
              comline_cur-=1

            continue

        if ord(k[0]) == KEY_CTRLW: # remove the last word
            # damn
            if comline_cur==0:
                continue

            #
            starting_cur = comline_cur
            # move the white space
            cur_char = comline[comline_cur-1]
            while cur_char.isspace() and comline_cur>0:
                comline_cur -= 1
                cur_char = comline[comline_cur-1]

            if comline_cur==0:
                comline = comline[starting_cur:]
                continue

            while not cur_char.isspace() and comline_cur>0:
                comline_cur -= 1
                cur_char = comline[comline_cur-1]

            comline = comline[:comline_cur] + comline[starting_cur:]

        elif k == "KEY_UP":
            pass
        elif k == "KEY_DOWN":
            pass
        elif k == "KEY_END":
            comline_cur = len(comline)
        elif k == "KEY_HOME":
            comline_cur = 0
        elif k == "KEY_NPAGE": # page down
            pass
        elif k == "KEY_PPAGE": # page up
            pass

        elif k == "kRIT3": # alt-right
            pass
        elif k == "kLFT3": # alt-left
            pass

        elif k == "kRIT5": # ctrl-right
            if comline_cur == len(comline):
                continue
            # last char -- move to the end
            elif comline_cur == len(comline)-1:
                comline_cur += 1
                continue

            comline_cur += 1

            # pass white space
            cur_char = comline[comline_cur]
            while cur_char.isspace() and comline_cur<len(comline):
                comline_cur += 1
                if comline_cur == len(comline):
                    break
                cur_char = comline[comline_cur]

            if comline_cur == len(comline):
                continue

            # pass letters
            cur_char = comline[comline_cur]
            while not cur_char.isspace() and comline_cur<len(comline):
                comline_cur += 1
                if comline_cur == len(comline):
                    break
                cur_char = comline[comline_cur]

            continue

        elif k == "kLFT5": # ctrl-left
            if comline_cur == 0:
                continue

            # pass white space
            cur_char = comline[comline_cur-1]
            while cur_char.isspace() and comline_cur>0:
                comline_cur -= 1
                cur_char = comline[comline_cur-1]

            if comline_cur == 0:
                continue

            # pass letters
            cur_char = comline[comline_cur-1]
            while not cur_char.isspace() and comline_cur>0:
                comline_cur -= 1
                cur_char = comline[comline_cur-1]

        elif k == "KEY_LEFT":
            comline_cur -= 1 if comline_cur>0 else 0
        elif k == "KEY_RIGHT":
            comline_cur += 1 if comline_cur<len(comline) else 0

        # if printable
        elif k.isprintable():
            comline = comline[:comline_cur] + k + comline[comline_cur:] # chr(k)
            comline_cur+=1

    #stdscr.addstr(cur_y, 0, 'Hello, curses!')

    #cur_y = 0
    #stdscr.addstr(cur_y, 0, 'Hello, curses!')
    #cur_y += 1
    #stdscr.addstr(cur_y, 0, 'Hello, curses!')

    cur.puts('Hello, curses!')
    cur.puts('Hello, curses 2!')

    c = stdscr.getch()
    cur.puts(f'c -> {chr(c)}')

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

    cur.commandline(cur.current_input_validator)

    # just pause it
    stdscr.getch()


wrapper(main)

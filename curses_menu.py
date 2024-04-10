"""
https://wasimlorgat.com/posts/editor
https://hyperskill.org/blog/post/introduction-to-the-curses-library-in-python-text-based-interfaces
https://stackoverflow.com/questions/18551558/how-to-use-terminal-color-palette-with-curses
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
selected_opts = set()

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

from collections import namedtuple
MatchString = namedtuple("MatchString", 'content ismatch')

DEBUG=False

FIELD_SEPARATOR='.'

def match_string_to_substr_selector(substr):
  def selector(cur_matches: list, stdscr, prev_offset, debug_line) -> list:
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
    def __init__(self):
        self.comline = ""
        self.cur_pos = 0
    def __repr__(self):
        return f'Comline()'
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

        elif k == "kRIT5": # ctrl-right
            self.moveto_right_word()

        elif k == "kLFT5": # ctrl-left
            self.moveto_left_word()

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
    comline = Comline()

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

    prompt = "> "
    k = " "
    cur_select_cursor = 0
    while True:
        stdscr.erase()

        stdscr.addstr(0, 0, f'{prompt}{comline}')
        #stdscr.addstr(1, 0, comline)
        stdscr.addstr(1, 0, ' '*(len(prompt) + comline.cur_pos) + "^")
        #stdscr.refresh()

        stdscr.addstr(4, 0, f'user cur: {comline.cur_pos} {len(comline)}')
        if ord(k[0]) != 0:
            stdscr.addstr(5, 0, f'user char: {k} {len(k)} {ord(k[0])} {ord(k[0]) == KEY_ESC}')

        else:
            stdscr.addstr(5, 0, f'user char: <null_character> {len(k)} {ord(k[0])} {ord(k[0]) == KEY_ESC}')

        # act on the user input as a set of substrings to find
        patterns = comline.split()

        # seave through the substrings
        if patterns:
            matched_opts = []
            for opt_num, opt in enumerate(opts):
                prev_offset = 0

                debug_line = opt_num
                if DEBUG:
                    stdscr.addstr(20+debug_line, prev_offset, opt)
                    prev_offset += 3 + len(opt)

                matches = match_string_to_selectors(opt, patterns, stdscr, debug_line, prev_offset)
                if matches: matched_opts.append((opt_num, matches))

        else:
            matched_opts = [(i, [MatchString(o, False)]) for i, o in enumerate(opts)]

        if cur_select_cursor >= len(matched_opts):
            cur_select_cursor = len(matched_opts) - 1
            # it will make the cursor negative when there are no matches

        if cur_select_cursor < 0 and len(matched_opts) > 0:
            cur_select_cursor = 0

        line_offset = 8
        for matched_o_num, (opt_num, matched_o) in enumerate(matched_opts):
            # split into substrings
            if matched_o_num >= __max_y: # if it goes outside the screen
                break

            if matched_o_num == cur_select_cursor:
                select_prompt = '> '

            else:
                select_prompt = '  '

            if opt_num in selected_opts:
                line_opt = styleSelectLine
            else:
                line_opt = styleNormalText

            # Print the matched options
            stdscr.addstr(line_offset+matched_o_num, 0, select_prompt)
            for substr in matched_o:
                opt = line_opt | (styleMatchedText if substr.ismatch else styleNormalText)
                stdscr.addstr(substr.content, opt)

        # Print selected options (debugging?)
        for i, sel_opt_num in enumerate(selected_opts):
            stdscr.addstr(20+i, 0, opts[sel_opt_num])

        stdscr.move(0, len(prompt) + comline.cur_pos)

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

        elif k == "KEY_NPAGE": # page down
            pass
        elif k == "KEY_PPAGE": # page up
            pass

        elif k == "kUP3": # alt-up
            pass
        elif k == "kDN3": # alt-down
            pass

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

        screen.addstr(0, 0, f'{prompt}{comline}')
        screen.addstr(1, 0, ' '*(len(prompt) + comline.cur_pos) + "^")
        screen.addstr(2, 0, 'just printing the selected options, and no action on ENTER')
        screen.addstr(3, 0, f'writing: {action_writing_output}')
        screen.addstr(4, 0, f'{time()}')

        screen.move(0, len(prompt) + comline.cur_pos)

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

def action_view(screen, options):
    line_offset = 20
    for i, opt in enumerate(options):
        screen.addstr(line_offset+i, 0, opt)

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


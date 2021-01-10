"""
Simple webVTT validation module based on https://github.com/w3c/webvtt.js
"""

from dataclasses import dataclass
import re

default_cue_settings = {
    'direction': 'horizontal',
    'snap_to_lines': True,
    'line_position': 'auto',
    'line_align': 'start',
    'text_position': 'auto',
    'position_align': 'auto',
    'size': 100,
    'alignment': 'center',
}

@dataclass
class Cue():
    id: str = ''
    start_time: int = 0
    end_time: int = 0
    pause_on_exit: bool = False
    direction: str = 'horizontal'
    snap_to_lines: bool = True
    line_position: str = 'auto'
    line_align: str = 'start'
    text_position: str = 'auto'
    position_align: str = 'auto'
    size: int = 100
    alignment: str = 'center'
    text: str = ''
    tree: bool = None
    non_serializable: bool = False

class WebVTTParser():

    def __init__(self, entities: dict={}) -> None:
        super().__init__()
        self.entities = entities or {
                '&amp': '&',
                '&lt': '<',
                '&gt': '>',
                '&lrm': '\u200e',
                '&rlm': '\u200f',
                '&nbsp': '\u00A0'
        }

    def parse(self, input_vtt: str, mode: str='') -> list:
        # global search and replace for \0
        lf = '\u000A'
        input_vtt = input_vtt.replace('\u0000', '\uFFFD')
        input_vtt = input_vtt.replace('\u000D\u000A', lf)
        input_vtt = input_vtt.replace('\u000D', lf)

        errors = []
        cues = []
        line_pos = 1
        lines = { key:value for key, value in enumerate(input_vtt.split(sep='\n'), start=1) }
        already_collected = False

        def err(message: str) -> None:
            errors.append({'line': line_pos, 'message': message  })

        line = lines.get(line_pos)
        line_length = len(line)
        signature = 'WEBVTT'
        bom = 0
        signature_length = len(signature)

        # Byte order mark
        if line[0]=='\ufeff':
            bom = 1
            signature_length += 1

        # SIGNATURE
        if (
            line_length < signature_length or
            line.find(signature) != 0+bom or
            line_length > signature_length and
            line[signature_length] != ' ' and
            line[signature_length] != '\t'
        ):
            err(f'No valid signature. (File needs to start with "{signature}".')

        line_pos += 1

		# HEADER
        while lines.get(line_pos) != '' and lines.get(line_pos) is not None:
            err('No blank line after the signature.')
            if lines.get(line_pos).find('-->') != -1:
                already_collected = True
                break
            line_pos +=1

        # CUE LOOP
        while lines.get(line_pos) is not None:
            while not already_collected and lines.get(line_pos) == '':
                line_pos += 1
            if not already_collected and lines.get(line_pos) is None:
                break

            # CUE CREATION
            cue =  Cue()
            parse_timings = True

            if lines[line_pos].find('-->') == -1:
                cue.id = lines[line_pos]

                # COMMENTS
                #   Not part of the specification's parser as these would just be ignored. However,
                #   we want them to be conforming and not get "Cue identifier cannot be standalone".
                if cue.id.startswith('NOTE'):
                    line_pos += 1
                    while lines.get(line_pos) != '' and lines.get(line_pos) is not None:
                        if lines.get(line_pos).find('-->') != -1:
                            err('Cannot have timestamp in a comment.')
                        line_pos += 1
                    continue

                line_pos += 1

                if lines.get(line_pos) == '' or lines.get(line_pos) is None:
                    err('Cue identifier cannot be standalone.')
                    continue

                if lines.get(line_pos).find('-->') == -1:
                    parse_timings = False
                    err('Cue identifier needs to be followed by timestamp.')
                    continue

            # TIMINGS
            already_collected = False
            timings = WebVTTCueTimingsAndSettingsParser(lines[line_pos], err)
            previous_cue_start = 0
            if len(cues)>0:
                previous_cue_start = cues[len(cues)-1].start_time

            if parse_timings and not timings.parse(cue, previous_cue_start):
                # BAD CUE

                cue = None
                line_pos += 1

                # BAD CUE LOOP
                while lines[line_pos] != '' and lines[line_pos] is not None:
                    if lines[line_pos].find('-->') != -1:
                        already_collected = True
                        break
                    line_pos += 1
                continue
            line_pos += 1

            #/* CUE TEXT LOOP */
            while lines.get(line_pos) != '' and lines.get(line_pos) is not None:
                if lines[line_pos].find('-->') != -1:
                    err('Blank line missing before cue.')
                    already_collected = True
                    break

                if cue.text != '':
                    cue.text += '\n'
                cue.text += lines[line_pos]
                line_pos += 1

            #/* CUE TEXT PROCESSING */
            cuetextparser = WebVTTCueTextParser(cue.text, err, mode, self.entities)
            cue.tree = cuetextparser.parse(cue.start_time, cue.end_time)
            cues.append(cue)

        #cues.sort(function(a, b) {
        #    if (a.startTime < b.startTime)
        #    return -1
        #    if (a.startTime > b.startTime)
        #    return 1
        #    if (a.endTime > b.endTime)
        #    return -1
        #    if (a.endTime < b.endTime)
        #    return 1
        #    return 0
        #})
        #/* END */

        return errors

class Struple(str):
    def __new__(cls, value: str):
        obj = str.__new__(cls, value)
        obj.__value = tuple(value)
        return obj

    def __getitem__(self, key) -> str:
        if isinstance(key, int):
            if key<0:
                key += len(self.__value)
            if key<0 or key>=len(self.__value):
                return None
            return self.__value[key]
        return super().__getitem__(key)

class WebVTTCueTimingsAndSettingsParser():
    def __init__(self, line: str, error_handler: callable) -> None:
        super().__init__()

        self.SPACE = (' ', '\t')
        self.DIGITS = '0123456789'
        self.line = Struple(line)
        self.pos = 0
        self.err = error_handler
        self.space_before_setting = True

    def skip(self, pattern: tuple):
        while self.line[self.pos] and self.line[self.pos] in pattern:
            self.pos += 1

    def collect(self, pattern) -> str:
        result_str = ''

        while self.line[self.pos] and self.line[self.pos] in pattern:
            result_str += self.line[self.pos]
            self.pos += 1
        return result_str

    def timestamp(self):
        units = 'minutes'
        val1 = 0
        val2 = 0
        val3 = 0
        val4 = 0
        #// 3
        if self.line[self.pos] is None:
            self.err('No timestamp found.')
            return
        #// 4
        if self.line[self.pos] not in self.DIGITS:
            self.err('Timestamp must start with a character in the range 0-9.')
            return
        #// 5-7
        val1 = self.collect(self.DIGITS)
        if len(val1) > 2 or int(val1) > 59:
            units = 'hours'
        #// 8
        if self.line[self.pos] != ':':
            self.err('No time unit separator found.')
            return
        self.pos += 1
        #// 9-11
        val2 = self.collect(self.DIGITS)
        if len(val2) != 2:
            self.err('Must be exactly two digits.')
            return
        #// 12
        if units == 'hours' or self.line[self.pos] == ':':
            if self.line[self.pos] != ':':
                self.err('No seconds found or minutes is greater than 59.')
                return
            self.pos += 1
            val3 = self.collect(self.DIGITS)
            if len(val3) != 2:
                self.err('Must be exactly two digits.')
                return
        else:
            if len(val1) != 2:
                self.err('Must be exactly two digits.')
                return
            val3 = val2
            val2 = val1
            val1 = '0'
        #// 13
        if self.line[self.pos] != '.':
            self.err('No decimal separator (".") found.')
            return
        self.pos += 1
        #// 14-16
        val4 = self.collect(self.DIGITS)
        if len(val4) != 3:
            self.err('Milliseconds must be given in three digits.')
            return
        #// 17
        if int(val2) > 59:
            self.err('You cannot have more than 59 minutes.')
            return
        if int(val3) > 59:
            self.err('You cannot have more than 59 seconds.')
            return

        return int(val1)*60*60 + int(val2)*60 + int(val3) + int(val4)/1000

    def parse_timestamp(self):
        ts = self.timestamp()
        if self.line[self.pos] is not None:
            self.err('Timestamp must not have trailing characters.')
            return None
        return ts

    def is_number(self, value: str) -> bool:
        from math import isinf, isnan
        try:
            num_value = float(value)
        except ValueError:
            return False
        return not (isnan(num_value) or isinf(num_value))

    def parse_settings(self, input: str, cue: Cue):
        settings = input.split()
        seen = []
        for i in range(len(settings)):
            if(settings[i] == ''):
                continue

            index = settings[i].find(':')
            setting = settings[i][:index]
            value = settings[i][index+1:]

            if setting in seen:
                self.err('Duplicate setting.')
            seen.append(setting)

            if value=='':
                self.err('No value for setting defined.')
                return

            if setting == 'vertical': # // writing direction
                if value not in  ('rl','lr'):
                    self.err('Writing direction can only be set to "rl" or "rl".')
                    continue
                cue.direction = value
            elif setting == 'line':  #// line position and optionally line alignment
                line_align = None
                if ',' in value:
                    comp = value.split(',')
                    value = comp[0]
                    line_align = comp[1]
                if not re.match(r'^[-\d](\d*)(\.\d+)?%?$', value):
                    self.err('Line position takes a number or percentage.')
                    continue
                if value.find('-', start=1) != -1:
                    self.err('Line position can only have "-" at the start.')
                    continue
                if value.find('%') != -1 and value.find('%') != len(value)-1:
                    self.err('Line position can only have "%" at the end.')
                    continue
                if value[0] == '-' and value[-1] == '%':
                    self.err('Line position cannot be a negative percentage.')
                    continue
                num_val = value
                is_percent = False
                if value[-1] == '%':
                    is_percent = True
                    num_val = value[0:-1]
                    if(int(num_val, 10) > 100):
                        self.err('Line position cannot be >100%.')
                        continue
                if not self.is_number(num_val):
                    self.err('Line position needs to be a number')
                    continue
                if line_align != None:
                    if line_align not in ('start', 'center', 'end'):
                        self.err('Line alignment needs to be one of start, center or end')
                        continue
                    cue.line_align = line_align
                cue.snap_to_lines = not is_percent
                cue.line_position = float(num_val)
                if str(float(num_val) != num_val):
                    cue.non_serializable = True
            elif setting == 'position': # // text position and optional positionAlign
                position_align = None
                if ',' in value:
                    comp = value.split(',')
                    value = comp[0]
                    position_align = comp[1]
                if value[-1] != '%':
                    self.err('Text position must be a percentage.')
                    continue
                num_val = value[:-1]
                if not self.is_number(num_val):
                    self.err('Line position needs to be a number')
                    continue
                if int(num_val)>100 or int(num_val)<0:
                    self.err('Text position needs to be between 0 and 100%.')
                    continue
                if position_align is not None:
                    if position_align not in ('line-left', 'center', 'line-right'):
                        self.err('Position alignment needs to be one of line-left, center or line-right')
                        continue
                    cue.position_align = position_align
                cue.text_position = float(num_val)
            elif setting == 'size': # // size
                if value[-1] != '%':
                    self.err('Size must be a percentage.')
                    continue
                size = value[:-1]
                if int(size)>100:
                    self.err('Size cannot be >100%.')
                    continue
                if size is None: # undefined || size === "" || isNaN(size)) {
                    self.err('Size needs to be a number')
                    size = 100
                    continue
                else:
                    size = float(size)
                    if size<0 or size>100:
                        self.err('Size needs to be between 0 and 100%.')
                        continue
                cue.size = size
            elif setting=='align': # // alignment
                align_values = ('start', 'center', 'end', 'left', 'right')
                if value not in align_values:
                    self.err(f'Alignment can only be set to one of {align_values}.')
                    continue
                cue.alignment = value
            else:
                self.err('Invalid setting.')

    def parse(self, cue: Cue, previous_cue_start: int):
        self.skip(self.SPACE)

        cue.start_time = self.timestamp()
        if cue.start_time is None:
            return
        if cue.start_time < previous_cue_start:
            self.err('Start timestamp is not greater than or equal to start timestamp of previous cue.')
        if self.line[self.pos] not in self.SPACE:
            self.err('Timestamp not separated from "-->" by whitespace.')
        self.skip(self.SPACE)
        #// 6-8
        if self.line[self.pos] != '-':
            self.err('No valid timestamp separator found.')
            return

        self.pos += 1
        if self.line[self.pos] != '-':
            self.err('No valid timestamp separator found.')
            return
        self.pos += 1
        if self.line[self.pos] != '>':
            self.err('No valid timestamp separator found.')
            return
        self.pos += 1
        if self.line[self.pos] not in self.SPACE:
            self.err('"-->" not separated from timestamp by whitespace.')
        self.skip(self.SPACE)
        cue.end_time = self.timestamp()
        if cue.end_time is None:
            return
        if cue.end_time <= cue.start_time:
            self.err('End timestamp is not greater than start timestamp.')
        if self.line[self.pos] not in self.SPACE:
            self.space_before_setting = False
        self.skip(self.SPACE)
        self.parse_settings(self.line[self.pos:], cue)
        return True

class WebVTTCueTextParser():
    def __init__(self, line, error_handler: callable, mode: str, entities: dict) -> None:
        super().__init__()
        self.line = Struple(line)
        self.pos: int = 0
        self.mode: str = mode
        self.entities: dict = entities
        self.error_handler: callable = error_handler

    def err(self, message: str) -> None:
        if self.mode != 'metadata':
            self.error_handler(message)

    def parse(self, cue_start, cue_end):
        result = {'children':[]}
        current = result
        timestamps = []

        def remove_cycles(tree: dict) -> dict:
            cycleless_tree = {**tree}
            if tree.get('children'):
                cycleless_tree['children'] = map(remove_cycles, tree['children'])
            cycleless_tree.pop('parent', None)
            return cycleless_tree

        def attach(token) -> None:
            nonlocal current
            data = {
                'type': 'object',
                'name': token[1],
                'classes':token[2],
                'children':[],
                'parent': current
            }
            current['children'].append(data)
            current = current['children'][len(current['children'])-1]

        def in_scope(name: str) -> bool:
            node = current
            while node:
                if node.get('name') == name:
                    return True
                node = node.get('parent')
            return False

        while self.line[self.pos] is not None:
            token = self.next_token()
            if token[0] == 'text':
                current['children'].append({'type':'text', 'value':token[1], 'parent':current})
            elif token[0] == 'start tag':
                if self.mode == 'chapters':
                    self.err('Start tags not allowed in chapter title text.')
                name = token[1]
                if name != 'v' and name != 'lang' and token[3] != '':
                    self.err('Only <v> and <lang> can have an annotation.')
                if name in ('c', 'i', 'b', 'u', 'ruby'):
                    attach(token)
                elif name == 'rt' and current['name'] == 'ruby':
                    attach(token)
                elif name == 'v':
                    if in_scope('v'):
                        self.err('<v> cannot be nested inside itself.')
                    attach(token)
                    current['value'] = token[3] #// annotation
                    if not token[3]:
                        self.err('<v> requires an annotation.')
                elif name == 'lang':
                    attach(token)
                    current['value'] = token[3] #// language
                else:
                    self.err('Incorrect start tag.')
            elif token[0] == 'end tag':
                if self.mode == 'chapters':
                    self.err('End tags not allowed in chapter title text.')
                #// XXX check <ruby> content
                if token[1] == current['name']:
                    current = current['parent']
                elif token[1] == 'ruby' and current['name'] == 'rt':
                    current = current['parent']['parent']
                else:
                    self.err('Incorrect end tag.')
            elif token[0] == 'timestamp':
                if self.mode == 'chapters':
                    self.err('Timestamp not allowed in chapter title text.')
                timings = WebVTTCueTimingsAndSettingsParser(token[1], self.err)
                timestamp = timings.parse_timestamp()
                if timestamp is not None:
                    if(timestamp <= cue_start or timestamp >= cue_end):
                        self.err('Timestamp must be between start timestamp and end timestamp.')
                    if(len(timestamps) > 0 and timestamps[len(timestamps)-1] >= timestamp):
                        self.err('Timestamp must be greater than any previous timestamp.')
                    current['children'].append({'type':'timestamp', 'value':timestamp, 'parent':current})
                    timestamps.append(timestamp)

        while current.get('parent'):
            if current.get('name') != 'v':
                self.err('Required end tag missing.')
            current = current.get('parent')

        return remove_cycles(result)

    def next_token(self) -> tuple:
        state = 'data'
        result = ''
        buffer = ''
        classes = []

        def from_char_code(*args: int) -> str:
            return ''.join(map(chr, args))

        while self.line[self.pos-1] is not None or self.pos == 0:
            c = self.line[self.pos]
            if state == 'data':
                if c == '&':
                    buffer = c
                    state = 'escape'
                elif c == '<' and result == '':
                    state = 'tag'
                elif c == '<' or c is None:
                    return ('text', result)
                else:
                    result += c
            elif state == 'escape':
                if c == '<' or c is None:
                    self.err('Incorrect escape.')
                    m = re.search(r'^&#([0-9]+)$', buffer)
                    if m:
                        result += from_char_code(int(m[1]))
                    else:
                        if self.entities.get(buffer):
                            result += self.entities.get(buffer)
                        else:
                            result += buffer
                    return ('text', result)
                elif c == '&':
                    self.err('Incorrect escape.')
                    result += buffer
                    buffer = c
                elif re.search(r'[a-z#0-9]', c, flags=re.IGNORECASE):
                    buffer += c
                elif c == ';':
                    m = re.match(r'^&#(x?[0-9]+)$', buffer)
                    if m:
                        if 'x' in m[1]:
                            result += from_char_code(int('0'+m[1], 16))
                        else:
                            result += from_char_code(int(m[1]))
                    elif self.entities.get(buffer + c):
                        result += self.entities.get(buffer + c)
                    elif k := [*filter(lambda x: buffer.startswith(x), self.entities.keys())]:
                        result += self.entities[k[0]] + buffer[len(k[0]):]+ c
                    else:
                        self.err('Incorrect escape.')
                        result += buffer + ';'
                    state = 'data'
                else:
                    self.err('Incorrect escape.')
                    result += buffer + c
                    state = 'data'
            elif state == 'tag':
                if c in ' \t\n\f':
                    state = 'start tag annotation'
                elif c == '.':
                    state = 'start tag class'
                elif c == '/':
                    state = "end tag"
                elif re.search(r'\d', c):
                    result = c
                    state = 'timestamp tag'
                elif c == '>' or c is None:
                    if c == '>':
                        self.pos += 1
                    return ('start tag', '', [], '')
                else:
                    result = c
                    state = 'start tag'
            elif state == 'start tag':
                if c in ' \t\f':
                    state = 'start tag annotation'
                elif c == '\n':
                    buffer = c
                    state = 'start tag annotation'
                elif c == '.':
                    state = 'start tag class'
                elif c == '>' or c is None:
                    if c == '>':
                        self.pos +=1
                    return ('start tag', result, [], '')
                else:
                    result += c
            elif state == 'start tag class':
                if c in ' \t\f':
                    if buffer:
                        classes.append(buffer)
                    buffer = ''
                    state = 'start tag annotation'
                elif c == '\n':
                    if buffer:
                        classes.append(buffer)
                    buffer = c
                    state = 'start tag annotation'
                elif c == '.':
                    if buffer:
                        classes.append(buffer)
                    buffer = ''
                elif c == '>' or c is None:
                    if c == '>':
                        self.pos += 1
                    if buffer:
                        classes.append(buffer)
                    return ('start tag', result, classes, '')
                else:
                    buffer += c
            elif state == 'start tag annotation':
                if c == '>' or c is None:
                    if c == '>':
                        self.pos += 1
                    buffer = ' '.join(buffer.split())
                    return ('start tag', result, classes, buffer)
                else:
                    buffer +=c
            elif state == 'end tag':
                if c == '>' or c is None:
                    if c == '>':
                        self.pos +=1
                    return ('end tag', result)
                else:
                    result += c
            elif state == 'timestamp tag':
                if c == '>' or c is None:
                    if c == '>':
                        self.pos += 1
                    return ('timestamp', result)
                else:
                    result += c
            else:
                self.err('Never happens.') #// The joke is it might.
            #// 8
            self.pos += 1
        return ()

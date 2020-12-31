"""
Simple webVTT validation module based on https://github.com/w3c/webvtt.js
"""

from dataclasses import dataclass

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

#            NEWLINE = r'\r\n|\r|\n',
        def err(message: str) -> None:
            errors.append({'line': line_pos, 'message': message  })

        line = lines.get(line_pos)
        total_lines = len(lines)
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
            #var cuetextparser = new WebVTTCueTextParser(cue.text, err, mode, this.entities)
            #cue.tree = cuetextparser.parse(cue.startTime, cue.endTime)
            #cues.push(cue)

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

class StringTuple():
    def __init__(self, value: str) -> None:
        self.__value = tuple(value)

    def __getitem__(self, key):
        try:
            return self.__value[key]
        except IndexError:
            return None

class WebVTTCueTimingsAndSettingsParser():
    def __init__(self, line: str, error_handler: callable) -> None:
        super().__init__()

#        NOSPACE = /[^\u0020\t\f]/,
        self.SPACE = (' ', '\t')
        self.DIGITS = '0123456789'
        self.line = StringTuple(line)
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
            return
        return ts

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

#        self.parse_settings(self.line[self.pos:], cue)

        return True

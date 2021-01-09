
import pytest
from webvtt import WebVTTParser
from pprint import pprint

good_vtt_data ="""WEBVTT

1
00:00:00.500 --> 00:00:02.000
<c.yellow.bg_blue>This is yellow text on a blue background</c>

2
00:00:02.500 --> 00:00:04.300
and the way we access it is changing stuff position:45%,line-right align:center size:35%
"""

bad_vtt_data ="""WEBVTT

00:00:00.500 --> 00:00:02.000
The Web is always changing & changing

00:00:02.500 --> 00:00:04.300
and the way we access it is changing

00:00:05.500 --> 00:00:06.300 position:10%,line-left align:left size:35%
Where did he go?

00:00:13.000 --> 00:00:16.500 position:90% align:right size:35%
I think he went down this lane.

00:00:14.000 --> 00:00:16.500 position:45%,line-right align:center size:135
What are you waiting for?
"""

def test_validate_header_valid():
    parser = WebVTTParser()
    valid_header = 'WEBVTT'
    result = parser.parse(valid_header)
    assert result == []
    return result

def test_validate_header_invalid():
    parser = WebVTTParser()
    broken_header = 'NO_WEBVTT'
    result = parser.parse(broken_header)
    assert result != []
    return result

def test_validate_cues_valid():
    parser = WebVTTParser()
    result = parser.parse(good_vtt_data)
    assert result == []
    return result

def test_validate_cues_invalid():
    parser = WebVTTParser()
    result = parser.parse(bad_vtt_data)
    assert result != []
    return result

if __name__ == '__main__':
    pprint(test_validate_cues_invalid())

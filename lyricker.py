#!/usr/bin/python3
import io
import json
import re
import urllib.parse

from flask import Flask, request, Response
import requests


kana_single = {  # か゚  き゚  く゚  け゚  こ゚ not implemented
    'あ': '아', 'い': '이', 'う': '우', 'え': '에', 'お': '오',
    'か': '카', 'き': '키', 'く': '쿠', 'け': '케', 'こ': '코',
    'さ': '사', 'し': '시', 'す': '스', 'せ': '세', 'そ': '소',
    'た': '타', 'ち': '치', 'つ': '츠', 'て': '테', 'と': '토',
    'な': '나', 'に': '니', 'ぬ': '누', 'ね': '네', 'の': '노',
    'は': '하', 'ひ': '히', 'ふ': '후', 'へ': '헤', 'ほ': '호',
    'ま': '마', 'み': '미', 'む': '무', 'め': '메', 'も': '모',
    'や': '야', 'ゆ': '유', 'よ': '요',
    'ら': '라', 'り': '리', 'る': '루', 'れ': '레', 'ろ': '로',
    'わ': '와', 'ゐ': '위', 'ゑ': '에', 'を': '오',

    'が': '가', 'ぎ': '기', 'ぐ': '구', 'げ': '게', 'ご': '고',
    'ざ': '자', 'じ': '지', 'ず': '즈', 'ぜ': '제', 'ぞ': '조',
    'だ': '다', 'ぢ': '지', 'づ': '즈', 'で': '데', 'ど': '도',
    'ば': '바', 'び': '비', 'ぶ': '부', 'べ': '베', 'ぼ': '보',

    'ぱ': '파', 'ぴ': '피', 'ぷ': '푸', 'ぺ': '페', 'ぽ': '포',
}

kana_before_yo_on = [
    '키',
    '시',
    '치',
    '니',
    '히',
    '미',
    '리',

    '기',
    '지',
    '비',

    '피',
]

yo_on = {
    'ゃ': 'ㅑ',
    'ゅ': 'ㅠ',
    'ょ': 'ㅛ',
}

leftovers = {
    'ぁ': '아',
    'ぃ': '이',
    'ぅ': '우',
    'ぇ': '에',
    'ぉ': '오',

    'ゎ': '와',
}

punctuation = {
    'ー': '-',
    '！': '!',
    '？': '?',
    '“': '"',
    '”': '"',
    '　': ' ',
    '、': ',',
    '。': '.',
    '（': '(',
    '）': ')',
}

regex_ascii = re.compile(r'^[\x00-\x7F]+$')

app = Flask(__name__)


@app.route('/')
def index():
    return '''<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8">
        <title>일본어 노래 가사 자동 번역기</title>
    </head>
    <body>
        <form action="/" method="post">
            <input type="submit" value="이 가사를 번역 (시간이 좀 걸립니다)">
            <br>
            <textarea name="lyrics" rows="40" cols="80">
            </textarea>
            <br>
            <input type="submit" value="이 가사를 번역 (시간이 좀 걸립니다)">
        </form>
    </body>
</html>'''


@app.route('/robots.txt')
def robot():
    return Response('''User-agent: *
Disallow: /''', mimetype='text/plain')


@app.route('/', methods=['POST'])
def convert():
    transcript = io.StringIO()
    for line in map(str.strip, request.form['lyrics'].strip().splitlines()):
        if line:
            transcript.write(line)
            transcript.write('\n')

            if regex_ascii.match(line):
                for _ in range(2):
                    transcript.write(line)
                    transcript.write('\n')
            else:
                transcript.write(get_line_pronounciation(line))
                transcript.write('\n')
                transcript.write(
                    translate_ntranstalk(
                        'j2k', line, '1', '1'
                    ).replace(' "', '"')
                )
                transcript.write('\n')
        else:
            transcript.write('\n')
        transcript.write('\n')
    result = io.StringIO()
    result.write('''<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8">
        <title>일본어 노래 가사 자동 번역기</title>
    </head>
    <body>
        <div>''')
    for line in transcript.getvalue().strip().splitlines():
        result.write('            ')
        result.write(line)
        result.write('<br>')
        result.write('\n')
    result.write('''        </div>
    </body>
</html>''')
    return result.getvalue()


def get_line_pronounciation(line):
    pronounciation = io.StringIO()
    syllable = io.StringIO()
    for char in yomitan(line):
        syllable_current = syllable.getvalue()
        if char in punctuation:
            pronounciation.write(syllable_current)
            pronounciation.write(punctuation[char])
            syllable = io.StringIO()
        elif syllable_current and syllable_current[-1] == 'ん':
            last_char = break_hangul(syllable_current[-2])
            pronounciation.write(syllable_current[0:-2])
            if char in kana_single:
                pronounciation.write(
                    assemble_hangul(
                        last_char[0], last_char[1], 'ㄴ'
                    )
                )  # fix needed to distinguish n and m etc. sounds
                syllable = io.StringIO()
                syllable.write(kana_single[char])
            else:
                pronounciation.write(
                    assemble_hangul(
                        last_char[0], last_char[1], 'ㅇ'
                    )
                )
                pronounciation.write(char)  # default
                syllable = io.StringIO()
        elif (
            not syllable_current
            or break_hangul(syllable_current[-1])[2]
                ):
            if char in kana_single:
                pronounciation.write(syllable_current)
                syllable = io.StringIO()
                syllable.write(kana_single[char])
            else:
                pronounciation.write(syllable_current)
                pronounciation.write(char)
        else:
            if char in kana_single:
                pronounciation.write(syllable_current)
                syllable = io.StringIO()
                syllable.write(kana_single[char])
            elif char == "っ":
                last_char = break_hangul(syllable_current[-1])
                syllable = io.StringIO()
                syllable.write(syllable_current[0:-1])
                syllable.write(
                    assemble_hangul(
                        last_char[0], last_char[1], 'ㅅ'
                    )
                )
            elif char in yo_on:
                if syllable_current[-1] in kana_before_yo_on:
                    last_char = break_hangul(syllable_current[-1])
                    syllable = io.StringIO()
                    syllable.write(syllable_current[0:-1])
                    syllable.write(
                        assemble_hangul(
                            last_char[0], yo_on[char], ''
                        )
                    )
                else:
                    pronounciation.write(syllable_current)
                    pronounciation.write(char)
            elif char == "ん":
                syllable.write("ん")
            else:
                pronounciation.write(syllable_current)
                pronounciation.write(char)
                syllable = io.StringIO()
        pronounciation_current = pronounciation.getvalue()
        if (
            len(pronounciation_current) > 2
            and pronounciation_current[-1] in punctuation.values()
            and pronounciation_current[-2] == '챵'
                ):
            pronounciation = io.StringIO()
            pronounciation.write(pronounciation_current[0:-2])
            pronounciation.write('쨩')
            pronounciation.write(pronounciation_current[-1])
    syllable_current = syllable.getvalue()
    if syllable_current:
        if syllable_current[-1] == 'ん':
            last_char = break_hangul(syllable_current[-2])
            pronounciation.write(syllable_current[0:-2])
            pronounciation.write(
                assemble_hangul(last_char[0], last_char[1], 'ㅇ')
            )
        else:
            pronounciation.write(syllable_current)
        pronounciation_current = pronounciation.getvalue()
        if pronounciation_current[-1] == '챵':
            pronounciation = io.StringIO()
            pronounciation.write(pronounciation_current[0:-1])
            pronounciation.write('쨩')
    return pronounciation.getvalue()


def translate_ntranstalk(dir, query, highlight, hurigana):
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip,deflate,sdch',
        'Accept-Language': 'en-US,en;q=0.8',
        'Cache-Control': 'max-age=0',
        'charset': 'utf-8',
        'DNT': '1',
        'Origin': 'http://jpdic.naver.com',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Host': 'jpdic.naver.com',
        'IfModifiedSince': 'Thu, 1 Jan 1970 00:00:00 GMT',
        'Referer': 'http://jpdic.naver.com/trans.nhn',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/28.0.1500.95 Safari/537.36',
    }
    payload = {
        'dir': dir,
        'query': query,
        'highlight': highlight,
        'hurigana': hurigana,
    }
    r = requests.post(
        'http://jpdic.naver.com/transProxy.nhn',
        data=payload,
        headers=headers,
    )
    return json.loads(r.text)['resultData']


def yomitan(str):
    url = io.StringIO()
    url.write("http://yomi-tan.jp/api/yomi.php?ic=UTF-8&oc=UTF-8&k=h&n=1&t=")
    url.write(urllib.parse.quote(str, safe=''))
    r = requests.get(url.getvalue())
    r.encoding = 'utf-8'
    return r.text


cho_list = [
    'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ',
    'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
]
jung_list = [
    'ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ',
    'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ'
]
jong_list = [
    '', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ',
    'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
]


def break_hangul(char):
    code = ord(char) - 44032
    cho = code // 588
    jung = code % 588 // 28
    jong = code % 588 % 28
    return [cho_list[cho], jung_list[jung], jong_list[jong]]


def assemble_hangul(cho, jung, jong):
    return chr(
        44032
        + cho_list.index(cho) * 588
        + jung_list.index(jung) * 28
        + jong_list.index(jong)
    )


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)

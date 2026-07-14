# -*- coding:utf-8 -*-
"""业务组编码：由名称自动生成；非英文先译为英文再 slug。"""
import hashlib
import html
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r'[^a-z0-9]+')
_CJK_RE = re.compile(
    r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff'
    r'\u3040-\u30ff\uac00-\ud7af]'
)


def needs_english_translation(text):
    """含中日韩等字符时需要译成英文再编码。"""
    return bool(_CJK_RE.search(text or ''))


def slugify_code(text, max_len=48):
    """英文/拉丁文本 → 小写短横线编码。"""
    if not text:
        return ''
    folded = unicodedata.normalize('NFKD', text)
    folded = folded.encode('ascii', 'ignore').decode('ascii')
    folded = folded.lower().strip()
    slug = _SLUG_RE.sub('-', folded).strip('-')
    while '--' in slug:
        slug = slug.replace('--', '-')
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip('-')
    return slug


def translate_to_english(text, timeout=3.0):
    """
    将名称译为英文。优先 MyMemory（无新依赖，复用 requests）。
    失败返回原文本，由调用方决定 fallback。
    """
    text = (text or '').strip()
    if not text:
        return ''
    if not needs_english_translation(text):
        return text
    try:
        import requests

        resp = requests.get(
            'https://api.mymemory.translated.net/get',
            params={'q': text[:200], 'langpair': 'zh-CN|en-GB'},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return text
        data = resp.json() or {}
        translated = (
            (data.get('responseData') or {}).get('translatedText') or ''
        ).strip()
        if not translated:
            return text
        # API 偶发回原文或 INVALID；并解码 HTML 实体（如 R&amp;D）
        if translated.upper().startswith('INVALID'):
            return text
        return html.unescape(translated)
    except Exception as exc:
        logger.info('group code translate failed: %s', exc)
        return text


def fallback_code_from_name(name):
    digest = hashlib.sha1((name or '').encode('utf-8')).hexdigest()[:8]
    return 'g-%s' % digest


def generate_group_code(name, existing_codes=None, translate=True):
    """
    由名称生成唯一编码。
    existing_codes: 已占用 code 的可迭代集合；冲突时追加 -2、-3…
    translate: 单测可关并注入 mock。
    """
    name = (name or '').strip()
    if not name:
        return ''
    source = name
    if translate and needs_english_translation(name):
        source = translate_to_english(name)
    source = html.unescape(source or '')
    code = slugify_code(source)
    if not code or needs_english_translation(code):
        code = fallback_code_from_name(name)
    occupied = set(existing_codes or [])
    if code not in occupied:
        return code[:64]
    base = code[:60]
    n = 2
    while True:
        candidate = '%s-%s' % (base, n)
        if len(candidate) > 64:
            candidate = candidate[:64]
        if candidate not in occupied:
            return candidate
        n += 1
        if n > 9999:
            return fallback_code_from_name('%s-%s' % (name, n))[:64]

"""将开源词库 JSON / JSONL 解析为统一词条结构。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


@dataclass
class VocabEntry:
    word: str
    translations: List[str]
    pos: str = ""
    phrases: List[str] = None
    examples: List[str] = None

    def __post_init__(self):
        if self.phrases is None:
            self.phrases = []
        if self.examples is None:
            self.examples = []


def _clean_str(v: Any) -> str:
    return str(v or "").strip()


def parse_kylebing_json(path: Path) -> List[VocabEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"KyleBing JSON 应为数组: {path}")
    out: List[VocabEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        word = _clean_str(item.get("word"))
        if not word:
            continue
        translations = []
        pos = ""
        for tr in item.get("translations") or []:
            if not isinstance(tr, dict):
                continue
            t = _clean_str(tr.get("translation"))
            if t:
                translations.append(t)
            if not pos:
                pos = _clean_str(tr.get("type"))
        phrases = []
        for ph in item.get("phrases") or []:
            if not isinstance(ph, dict):
                continue
            p = _clean_str(ph.get("phrase"))
            pt = _clean_str(ph.get("translation"))
            if p:
                phrases.append(f"{p} — {pt}" if pt else p)
        out.append(VocabEntry(word=word, translations=translations, pos=pos, phrases=phrases))
    return out


def _extract_kajweb_entry(obj: dict) -> Optional[VocabEntry]:
    head = _clean_str(obj.get("headWord") or obj.get("word"))
    content = obj.get("content") or {}
    if isinstance(content, dict) and "word" in content:
        inner = content.get("word") or {}
        if isinstance(inner, dict):
            head = _clean_str(inner.get("wordHead")) or head
            content = inner.get("content") or content
    if not head:
        return None
    translations: List[str] = []
    pos = ""
    phrases: List[str] = []
    examples: List[str] = []
    if isinstance(content, dict):
        trans_block = content.get("trans") or content.get("translation") or {}
        if isinstance(trans_block, dict):
            for tr in trans_block.get("trans") or trans_block.get("tranList") or []:
                if not isinstance(tr, dict):
                    continue
                t = _clean_str(tr.get("tranCn") or tr.get("descCn") or tr.get("translation"))
                if t:
                    translations.append(t)
                if not pos:
                    pos = _clean_str(tr.get("pos"))
        syno = content.get("syno") or {}
        if isinstance(syno, dict):
            for s in syno.get("synos") or []:
                if isinstance(s, dict):
                    t = _clean_str(s.get("tran"))
                    if t:
                        translations.append(t)
        sentence = content.get("sentence") or {}
        if isinstance(sentence, dict):
            for s in sentence.get("sentences") or []:
                if isinstance(s, dict):
                    en = _clean_str(s.get("sContent"))
                    cn = _clean_str(s.get("sCn"))
                    if en:
                        examples.append(f"{en} ({cn})" if cn else en)
        phrase = content.get("phrase") or {}
        if isinstance(phrase, dict):
            for p in phrase.get("phrases") or []:
                if isinstance(p, dict):
                    pv = _clean_str(p.get("pContent") or p.get("phrase"))
                    pc = _clean_str(p.get("pCn"))
                    if pv:
                        phrases.append(f"{pv} — {pc}" if pc else pv)
    if not translations:
        translations = ["（暂无中文释义）"]
    return VocabEntry(word=head, translations=translations, pos=pos, phrases=phrases, examples=examples)


def parse_kajweb_jsonl(path: Path) -> List[VocabEntry]:
    out: List[VocabEntry] = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        entry = _extract_kajweb_entry(obj)
        if not entry:
            continue
        key = entry.word.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out


def parse_tier_file(path: Path, source: str) -> List[VocabEntry]:
    if not path.is_file():
        raise FileNotFoundError(f"词库文件不存在: {path}（请先运行 scripts/download_english_curriculum_data.sh）")
    if source == "kylebing_json":
        return parse_kylebing_json(path)
    if source == "kajweb_pep_primary":
        return parse_kajweb_jsonl(path)
    raise ValueError(f"未知 source: {source}")


def chunk_entries(entries: List[VocabEntry], chunk_size: int) -> List[List[VocabEntry]]:
    if chunk_size <= 0:
        return [entries]
    return [entries[i : i + chunk_size] for i in range(0, len(entries), chunk_size)]


def entries_to_markdown(tier_title: str, batch_index: int, batch: List[VocabEntry]) -> str:
    lines = [f"# {tier_title} · 词汇第 {batch_index} 批", ""]
    for e in batch:
        lines.append(f"## {e.word}")
        if e.pos:
            lines.append(f"- **词性**: {e.pos}")
        if e.translations:
            lines.append(f"- **释义**: {'；'.join(e.translations[:5])}")
        if e.phrases:
            lines.append("- **短语**:")
            for p in e.phrases[:6]:
                lines.append(f"  - {p}")
        if e.examples:
            lines.append("- **例句**:")
            for ex in e.examples[:3]:
                lines.append(f"  - {ex}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"

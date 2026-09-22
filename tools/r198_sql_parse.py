# -*- coding: utf-8 -*-
"""r198 B2：作用域感知的 Oracle 旧方言 SQL 预解析器（修正 197 F01 缺陷）。

与 _scratch/r197_s2_parse.py 的区别（语义合同，tools/tests/test_r198_sql_parse.py 逐条锁定）：
- 查询块（query block）各自持有 FROM 表实例与别名作用域；相关子查询沿父链解析（T03）。
- 显式 JOIN 的类型按关键字方向记录（LEFT/RIGHT/FULL/CROSS/INNER/NATURAL + ON），
  Oracle (+) 记 null 补齐侧（plus_side），两者并存时如实分列（T01）。
- 布尔谓词树：只有同一 AND 节点内的等值谓词可合并复合键；OR 分支、不同查询块、
  不同布尔分支的谓词不合并（T02）。branch 记录 OR 分支路径。
- 自连接：同表不同别名=两个实例，边保留两侧实例角色（T04）。
- CTE/派生表：ref 标记 kind，物理表经定义溯源（physical_tables）；无法唯一溯源记 unresolved（T04）。
- 解析失败显式 unresolved，不猜边（T08）。

纯函数模块：无 IO、无全局状态，可独立测试。输出 dict 结构见 parse_sql。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

IDENT = r'[A-Za-z_\u4e00-\u9fff][\w$#\u4e00-\u9fff]*'
TABLE_NAME_PSEUDO = re.compile(r'^TABLE_NAME\d+$')

JOIN_RUN = re.compile(r'\b((?:(?:LEFT|RIGHT|FULL|INNER|CROSS|NATURAL)\s+)*(?:OUTER\s+)?JOIN)\b', re.IGNORECASE)
JOIN_TYPE_OF = {
    (): 'inner', ('LEFT',): 'left', ('RIGHT',): 'right', ('FULL',): 'full',
    ('INNER',): 'inner', ('CROSS',): 'cross', ('NATURAL',): 'natural',
}
RESERVED_ALIAS = {
    'WHERE', 'GROUP', 'ORDER', 'HAVING', 'UNION', 'MINUS', 'INTERSECT',
    'JOIN', 'LEFT', 'RIGHT', 'FULL', 'INNER', 'CROSS', 'OUTER', 'NATURAL', 'ON', 'USING',
    'AND', 'OR', 'NOT', 'SELECT', 'FROM', 'SET', 'CONNECT', 'START', 'WITH',
    'FOR', 'UPDATE', 'DELETE', 'INSERT', 'INTO', 'VALUES', 'MERGE', 'USING',
    'WHEN', 'THEN', 'ELSE', 'END', 'CASE', 'EXISTS', 'IN', 'BETWEEN', 'LIKE',
    'IS', 'NULL', 'AS', 'BY', 'ASC', 'DESC', 'DISTINCT', 'ALL', 'ROWNUM',
}

_TOKEN_RE = re.compile(
    r"""\s+|-(?:-[^\r\n]*)?|/\*.*?\*/|'(?:[^']|'')*'|"(?:[^"]|"")*"|[A-Za-z_\u4e00-\u9fff][\w$#\u4e00-\u9fff]*|\d+(?:\.\d+)?|\|\||::|>=|<=|<>|!=|=>|[-+*/<>=(),.;@?]""",
    re.DOTALL | re.VERBOSE,
)


def tokenize(text: str):
    """List of (kind, text, start); kind: ws/comment/str/ident/num/op."""
    toks, i, n = [], 0, len(text)
    while i < n:
        m = _TOKEN_RE.match(text, i)
        if not m:
            toks.append(('op', text[i], i))
            i += 1
            continue
        t = m.group(0)
        i = m.end()
        if t.isspace():
            k = 'ws'
        elif t.startswith('--') or t.startswith('/*'):
            k = 'comment'
        elif t[0] in '\'"':
            k = 'str'
        elif t[0].isalpha() or t[0] == '_' or '\u4e00' <= t[0] <= '\u9fff':
            k = 'ident'
        elif t[0].isdigit():
            k = 'num'
        else:
            k = 'op'
        toks.append((k, t, m.start()))
    return toks


_FW_MAP = str.maketrans({
    '（': '(', '）': ')', '，': ',', '、': ' ', '；': ';', '：': ':',
    '“': '"', '”': '"', '‘': "'", '’': "'",
    '\u3000': ' ', '　': ' ',
})
_SQL_KW_IN_STR = re.compile(r'\b(FROM|WHERE|AND|OR|JOIN|SELECT|UNION|GROUP|HAVING|ON|MINUS)\b', re.IGNORECASE)


def _quotes_safe(clean: str) -> bool:
    """脱敏语料常见 `'?` 未闭合引号：配对不平衡或字符串吞 SQL 关键字时判定不安全。"""
    if clean.count("'") % 2:
        return False
    i, n = 0, len(clean)
    while i < n:
        if clean[i] == "'":
            j = clean.find("'", i + 1)
            if j < 0:
                return False
            lit = clean[i + 1:j]
            if len(lit) > 200 or _SQL_KW_IN_STR.search(lit):
                return False
            i = j + 1
        else:
            i += 1
    return True


def strip_noise(text: str) -> str:
    """全角归一 + 注释换空格；引号不安全时结构性剥离引号（保留 ? 占位）。"""
    text = text.translate(_FW_MAP)
    out = []
    for kind, t, _ in tokenize(text):
        out.append(' ' if kind in ('ws', 'comment') else t)
    clean = ''.join(out)
    if not _quotes_safe(clean):
        clean = clean.replace("'", ' ')
    return clean


# ---------------------------------------------------------------------------
# Boolean predicate tree


@dataclass
class BoolNode:
    kind: str                          # 'and' | 'or' | 'leaf'
    children: list = field(default_factory=list)
    text: str = ''
    branch_ids: tuple = ()             # OR-branch path to this node (T02)

    def leaves(self):
        if self.kind == 'leaf':
            yield self
        for c in self.children:
            yield from c.leaves()

    def and_groups(self):
        """Yield lists of leaves that share one AND node (composite-key eligible)."""
        if self.kind == 'leaf':
            yield [self]
        elif self.kind == 'and':
            grp = []
            for c in self.children:
                if c.kind == 'leaf':
                    grp.append(c)
                else:
                    yield from c.and_groups()
            if grp:
                yield grp
        else:  # or
            for c in self.children:
                yield from c.and_groups()


def _split_top(s: str, kw: str):
    """Split on top-level token kw (word boundary for alpha kw, outside parens/strings)."""
    parts, depth, cur, i, n, in_str = [], 0, [], 0, len(s), None
    alpha = kw[0].isalpha()
    pat = re.compile((kw + r'(?![\w$#])') if alpha else re.escape(kw), re.IGNORECASE)
    while i < n:
        ch = s[i]
        if in_str:
            cur.append(ch)
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in '\'"':
            in_str = ch
            cur.append(ch)
            i += 1
            continue
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if depth == 0 and (ch == kw[0] if not alpha else (ch.isalpha() and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] in '_$#')))):
            m = pat.match(s, i)
            if m:
                parts.append(''.join(cur))
                cur = []
                i = m.end()
                continue
        cur.append(ch)
        i += 1
    parts.append(''.join(cur))
    return [p for p in (x.strip() for x in parts) if p]


def split_bool(span: str) -> BoolNode:
    """Parse predicate span into AND/OR tree (OR < AND precedence). Paren-aware."""
    if span.count('(') != span.count(')'):
        return BoolNode('leaf', text=span, branch_ids=('unbalanced',))

    def parse_or(s, branch):
        parts = _split_top(s, 'OR')
        if len(parts) == 1:
            return parse_and(s, branch)
        node = BoolNode('or', text=s)
        for i, p in enumerate(parts):
            node.children.append(parse_and(p, branch + (i,)))
        return node

    def parse_and(s, branch):
        # 括号包裹的子表达式：剥一层括号后按 OR 层级下钻（保持 OR 分支路径）
        t = s.strip()
        while t.startswith('(') and t.endswith(')') and _find_matching_paren(t, 0) == len(t) - 1:
            inner = t[1:-1]
            if not inner.strip():
                break
            t = inner.strip()
        parts = _split_top(t, 'AND')
        if len(parts) == 1:
            sub = _split_top(t, 'OR')
            if len(sub) > 1:
                node = BoolNode('or', text=t)
                for i, p in enumerate(sub):
                    node.children.append(parse_and(p, branch + (i,)))
                return node
            return BoolNode('leaf', text=t, branch_ids=branch)
        node = BoolNode('and', text=t)
        for p in parts:
            node.children.append(parse_and(p, branch))
        return node

    return parse_or(span, ())


# ---------------------------------------------------------------------------
# Blocks and refs


@dataclass
class Ref:
    instance_id: int
    block_id: str
    table: str                       # qualified upper（@dblink 保留在表名尾部）
    alias: str | None
    kind: str = 'table'              # table | subquery | cte | dblink
    sub_block: str | None = None
    cte_name: str | None = None


@dataclass
class Block:
    block_id: str
    parent: str | None
    kind: str                        # top | from_sub | where_sub | select_sub | cte | union_arm
    refs: list = field(default_factory=list)
    joins: list = field(default_factory=list)   # {'from','to','join_type','on_text','on_node','words'}
    where_text: str = ''
    where_node: BoolNode | None = None
    children: list = field(default_factory=list)


def _find_matching_paren(s: str, start: int) -> int:
    depth, i, n, in_str = 0, start, len(s), None
    while i < n:
        ch = s[i]
        if in_str:
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in '\'"':
            in_str = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _depth_before(s: str, pos: int) -> int:
    d, in_str = 0, None
    for i in range(pos):
        ch = s[i]
        if in_str:
            if ch == in_str:
                in_str = None
            continue
        if ch in '\'"':
            in_str = ch
        elif ch == '(':
            d += 1
        elif ch == ')':
            d -= 1
    return d


_REF_RE = re.compile(
    r'^(' + IDENT + r')(?:\s*\.\s*(' + IDENT + r'))?(?:\s*\.\s*(' + IDENT + r'))?'
    r'(?:\s*@\s*(' + IDENT + r'))?(?:\s+(?:AS\s+)?(' + IDENT + r'))?\s*$',
    re.IGNORECASE,
)


class Parser:
    def __init__(self, clean: str):
        self.clean = clean
        self.blocks: dict[str, Block] = {}
        self.cte_defs: dict[str, str] = {}
        self.n_block = 0
        self.n_inst = 0
        self.warnings: list[str] = []

    # -- structure ----------------------------------------------------------
    def parse(self) -> str:
        s = self.clean.strip()
        # 非查询前缀（create table X as / insert into / update / delete from）：
        # 裁剪到首个 SELECT/WITH；相关引用如无法解析将显式 unresolved
        if not re.match(r'^(SELECT|WITH)\b', s, re.IGNORECASE):
            m = re.search(r'\b(SELECT|WITH)\b', s, re.IGNORECASE)
            if m:
                self.warnings.append('prefix_trimmed:' + s[:30].strip())
                s = s[m.start():]
        # 整条语句被括号包裹（S1 切分产物/CREATE TABLE AS (...)）
        t = s
        while t.startswith('(') and t.endswith(')') and _find_matching_paren(t, 0) == len(t) - 1:
            t = t[1:-1].strip()
        self.clean = t
        return self._parse_query(self.clean, None, 'top')

    def _new_block(self, parent, kind) -> Block:
        self.n_block += 1
        bid = f'B{self.n_block}'
        b = Block(block_id=bid, parent=parent, kind=kind)
        self.blocks[bid] = b
        if parent is not None and parent in self.blocks:
            self.blocks[parent].children.append(bid)
        return b

    def _parse_query(self, s: str, parent, kind) -> str:
        arms = self._split_union(s)
        first = None
        for _, arm in arms:
            bid = self._parse_arm(arm, parent, 'union_arm' if len(arms) > 1 else kind)
            if first is None:
                first = bid
        return first

    def _split_union(self, s: str):
        parts, depth, i, n, start, in_str = [], 0, 0, len(s), 0, None
        pat = re.compile(r'(UNION\s+ALL|UNION|MINUS|INTERSECT)(?![\w$#])', re.IGNORECASE)
        while i < n:
            ch = s[i]
            if in_str:
                if ch == in_str:
                    in_str = None
                i += 1
                continue
            if ch in '\'"':
                in_str = ch
                i += 1
                continue
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            if depth == 0 and ch.isalpha() and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] in '_$#')):
                m = pat.match(s, i)
                if m:
                    parts.append((start, s[start:i]))
                    i += len(m.group(0))
                    start = i
                    continue
            i += 1
        parts.append((start, s[start:]))
        return [(a, b) for a, b in parts if b.strip()]

    def _parse_arm(self, s: str, parent, kind) -> str:
        blk = self._new_block(parent, kind)
        body = s.strip()
        # arm 自身被括号包裹（(select ...) union (select ...)）
        while body.startswith('(') and body.endswith(')') and _find_matching_paren(body, 0) == len(body) - 1:
            body = body[1:-1].strip()
        if re.match(r'^\s*WITH\b', body, re.IGNORECASE):
            body = self._parse_ctes(body, blk.block_id)
        segs = self._split_clauses(body)
        self._parse_from(blk, segs.get('FROM', ''))
        where_text = segs.get('WHERE', '')
        having_text = segs.get('HAVING', '')
        blk.where_text = re.sub(r'^\s*WHERE\s+', '', where_text.strip(), flags=re.IGNORECASE)
        blk.where_node = split_bool(blk.where_text) if blk.where_text else None
        # SELECT 列表 / WHERE / HAVING 中的 (SELECT ...) 子查询：建子块（相关引用可溯源父链）
        for src in (segs.get('SELECT', ''), blk.where_text, having_text):
            self._extract_subselects(src, blk.block_id)
        return blk.block_id

    def _parse_ctes(self, body: str, parent_bid: str) -> str:
        i = re.match(r'^\s*WITH\b', body, re.IGNORECASE).end()
        while True:
            m2 = re.compile(r'\s*(' + IDENT + r')\s*(\([^)]*\))?\s+AS\s*\(', re.IGNORECASE).match(body, i)
            if not m2:
                break
            name = m2.group(1).upper()
            p_open = body.index('(', m2.end() - 1)
            p_close = _find_matching_paren(body, p_open)
            if p_close < 0:
                self.warnings.append(f'cte {name}: unbalanced parens')
                break
            self.cte_defs[name] = self._parse_query(body[p_open + 1:p_close], parent_bid, 'cte')
            i = p_close + 1
            if i < len(body) and body[i] == ',':
                i += 1
                continue
            break
        return body[i:]

    def _split_clauses(self, body: str) -> dict:
        segs, marks = {}, []
        depth, i, n, in_str = 0, 0, len(body), None
        pat = re.compile(r'(SELECT|FROM|WHERE|GROUP\s+BY|HAVING|ORDER\s+BY|CONNECT\s+BY|START\s+WITH|MODEL|FOR\s+UPDATE|FETCH\s+FIRST)(?![\w$#])', re.IGNORECASE)
        while i < n:
            ch = body[i]
            if in_str:
                if ch == in_str:
                    in_str = None
                i += 1
                continue
            if ch in '\'"':
                in_str = ch
                i += 1
                continue
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            if depth == 0 and ch.isalpha() and (i == 0 or not (body[i - 1].isalnum() or body[i - 1] in '_$#')):
                m = pat.match(body, i)
                if m:
                    marks.append((i, m.group(0).upper()))
                    i += len(m.group(0))
                    continue
            i += 1
        for k, (pos, kw) in enumerate(marks):
            end = marks[k + 1][0] if k + 1 < len(marks) else len(body)
            segs.setdefault(kw.split()[0], body[pos:end])
        return segs

    def _extract_subselects(self, text: str, parent_bid: str):
        """Parse outermost ( SELECT ... ) spans in text as child blocks."""
        if not text:
            return
        spans = []
        for m in re.finditer(r'\(\s*SELECT\b', text, re.IGNORECASE):
            close = _find_matching_paren(text, m.start())
            if close < 0:
                self.warnings.append('subselect: unbalanced parens')
                continue
            spans.append((m.start(), close))
        outer = []
        last_end = -1
        for a, b in spans:  # spans are ordered by start
            if a > last_end:
                outer.append((a, b))
                last_end = b
        for a, b in outer:
            self._parse_query(text[a + 1:b], parent_bid, 'where_sub')

    # -- FROM ---------------------------------------------------------------
    def _parse_from(self, blk: Block, from_text: str):
        if not from_text.strip():
            return
        from_text = re.sub(r'^\s*FROM\b\s*', '', from_text.strip(), flags=re.IGNORECASE)
        for el in _split_top(from_text, ','):
            el = el.strip()
            if not el:
                continue
            runs = [m for m in JOIN_RUN.finditer(el) if _depth_before(el, m.start()) == 0]
            if not runs:
                self._add_ref(blk, el)
                continue
            head = el[:runs[0].start()].strip()
            cur = self._add_ref(blk, head) if head else None
            for i, m in enumerate(runs):
                seg = el[m.end():(runs[i + 1].start() if i + 1 < len(runs) else len(el))].strip()
                on_m = next((mm for mm in re.finditer(r'\b(ON|USING)\b', seg, re.IGNORECASE)
                             if _depth_before(seg, mm.start()) == 0), None)
                if on_m:
                    target_txt, on_txt = seg[:on_m.start()].strip(), seg[on_m.end():].strip()
                else:
                    target_txt, on_txt = seg, ''
                words = tuple(w for w in m.group(1).upper().split() if w != 'OUTER')
                jt = JOIN_TYPE_OF.get(tuple(w for w in words if w != 'JOIN'), 'inner')
                right = self._add_ref(blk, target_txt)
                blk.joins.append({'from': cur.instance_id if cur else None,
                                  'to': right.instance_id if right else None,
                                  'join_type': jt, 'words': list(words),
                                  'on_text': on_txt,
                                  'on_node': split_bool(on_txt) if on_txt else None})
                cur = right

    def _add_ref(self, blk: Block, txt: str) -> Ref | None:
        txt = txt.strip().rstrip(',').strip()
        if not txt:
            return None
        if txt.startswith('('):
            close = _find_matching_paren(txt, 0)
            if close < 0:
                self.warnings.append('unbalanced derived-table parens')
                return None
            inner = txt[1:close]
            rest = txt[close + 1:].strip()
            am = re.match(r'^(?:AS\s+)?(' + IDENT + r')\s*$', rest, re.IGNORECASE)
            alias = am.group(1).upper() if am else None
            sub = self._parse_query(inner, blk.block_id, 'from_sub')
            ref = Ref(self._next_inst(), blk.block_id, f'({alias or "SUB"})', alias, 'subquery', sub_block=sub)
            blk.refs.append(ref)
            return ref
        m = _REF_RE.match(txt)
        if not m:
            self.warnings.append(f'unparsed FROM element: {txt[:60]!r}')
            return None
        p1, p2, p3, dblink, alias = m.groups()
        parts = [p for p in (p1, p2, p3) if p]
        table = '.'.join(x.upper() for x in parts).replace('..', '.')
        if dblink:
            table = table + '@' + dblink.upper()
        if TABLE_NAME_PSEUDO.match(table) or table == 'DUAL':
            return None
        if alias and alias.upper() in RESERVED_ALIAS:
            alias = None
        alias = alias.upper() if alias else None
        if table in self.cte_defs:
            ref = Ref(self._next_inst(), blk.block_id, table, alias or table, 'cte',
                      sub_block=self.cte_defs[table], cte_name=table)
        else:
            ref = Ref(self._next_inst(), blk.block_id, table, alias,
                      'dblink' if dblink else 'table')
        blk.refs.append(ref)
        return ref

    def _next_inst(self) -> int:
        self.n_inst += 1
        return self.n_inst


# ---------------------------------------------------------------------------
# Leaf classification + edge extraction

EQ_LEAF = re.compile(
    r'^\s*\(?\s*' + IDENT + r'\s*\.\s*(' + IDENT + r')\s*(\(\+\))?\s*\)?\s*'
    r'=\s*\(?\s*' + IDENT + r'\s*\.\s*(' + IDENT + r')\s*(\(\+\))?\s*\)?\s*$',
    re.IGNORECASE,
)
BARE_EQ_LEAF = re.compile(r'^\s*(' + IDENT + r')\s*(\(\+\))?\s*=\s*(' + IDENT + r')\s*(\(\+\))?\s*$', re.IGNORECASE)
# 函数包裹键独立表达：alias.col = FUNC(alias.col)（或反向）；函数名单独记录
FUNC_EQ_A = re.compile(
    r'^\s*(' + IDENT + r')\s*\.\s*(' + IDENT + r')\s*(\(\+\))?\s*=\s*(' + IDENT + r')\s*\(\s*(' + IDENT + r')\s*\.\s*(' + IDENT + r')\s*(\(\+\))?\s*\)\s*$',
    re.IGNORECASE)
FUNC_EQ_B = re.compile(
    r'^\s*(' + IDENT + r')\s*\(\s*(' + IDENT + r')\s*\.\s*(' + IDENT + r')\s*(\(\+\))?\s*\)\s*=\s*(' + IDENT + r')\s*\.\s*(' + IDENT + r')\s*(\(\+\))?\s*$',
    re.IGNORECASE)
EQ_ALIAS_L = lambda col, t: re.match(r'^\s*\(?\s*(' + IDENT + r')\s*\.\s*' + re.escape(col), t, re.IGNORECASE)
EQ_ALIAS_R = lambda col, t: re.search(r'(' + IDENT + r')\s*\.\s*' + re.escape(col) + r'\s*(?:\(\+\))?\s*\)?\s*$', t, re.IGNORECASE)
CONST_LEAF = re.compile(
    r'^\s*(?:' + IDENT + r'\s*\.\s*)?(' + IDENT + r')\s*(>=|<=|<>|!=|=|>|<|LIKE)\s*('
    r'\?|' + IDENT + r'|\'[^\']*\'|"[^"]*"|\d+(?:\.\d+)?)\s*$',
    re.IGNORECASE,
)
NOT_LEAF = re.compile(r'^\s*NOT\b', re.IGNORECASE)


class Scope:
    """Alias resolution along the block chain (innermost first)."""

    def __init__(self, blocks, root_id):
        self.blocks = blocks
        self.chain = []
        b = root_id
        while b is not None:
            self.chain.append(b)
            b = blocks[b].parent

    def resolve(self, name):
        name = name.upper()
        for bid in self.chain:
            for r in self.blocks[bid].refs:
                if r.alias == name:
                    return r
            for r in self.blocks[bid].refs:
                if r.kind in ('table', 'dblink') and r.table.split('.')[-1].split('@')[0] == name:
                    return r
        return None


def parse_sql(text: str) -> dict:
    clean = strip_noise(text)
    p = Parser(clean)
    top = p.parse()
    edges, unresolved, filters = [], [], []

    def eq_parts(t):
        m = EQ_LEAF.match(t.strip())
        if not m:
            return None
        lcol, plus1, rcol, plus2 = m.groups()
        lm, rm = EQ_ALIAS_L(lcol, t.strip()), EQ_ALIAS_R(rcol, t.strip())
        if not lm or not rm:
            return None
        return lm.group(1).upper(), lcol.upper(), plus1, rm.group(1).upper(), rcol.upper(), plus2

    def add_edge(node, blk, la, lcol, plus1, ra, rcol, plus2, join_ctx=None, edge_extra=None):
        if join_ctx is not None:
            by_inst = {r.instance_id: r for r in blk.refs}
            lr, rr = by_inst.get(join_ctx['from']), by_inst.get(join_ctx['to'])
            scope = Scope(p.blocks, blk.block_id)
            cand_l = lr if (lr and (lr.alias == la or lr.table.split('.')[-1].split('@')[0] == la)) else scope.resolve(la)
            cand_r = rr if (rr and (rr.alias == ra or rr.table.split('.')[-1].split('@')[0] == ra)) else scope.resolve(ra)
            extra = {'join_type': join_ctx['join_type'], 'source': 'on'}
        else:
            scope = Scope(p.blocks, blk.block_id)
            cand_l, cand_r = scope.resolve(la), scope.resolve(ra)
            extra = {'source': 'where'}
        if cand_l is None or cand_r is None:
            unresolved.append({'raw': node.text.strip()[:120], 'reason': 'alias-unresolved',
                               'la': la, 'ra': ra, 'block': blk.block_id,
                               'branch': list(node.branch_ids)})
            return
        if cand_l.instance_id == cand_r.instance_id:
            unresolved.append({'raw': node.text.strip()[:120], 'reason': 'same-instance',
                               'block': blk.block_id})
            return
        edges.append({
            'block': blk.block_id, 'branch': list(node.branch_ids),
            'l_instance': cand_l.instance_id, 'l_table': cand_l.table, 'l_kind': cand_l.kind,
            'l_alias': cand_l.alias, 'l_col': lcol,
            'r_instance': cand_r.instance_id, 'r_table': cand_r.table, 'r_kind': cand_r.kind,
            'r_alias': cand_r.alias, 'r_col': rcol,
            'plus_side': 'L' if plus1 else ('R' if plus2 else None),
            'and_group': group_of.get(id(node)),
            'raw': node.text.strip(), **extra, **(edge_extra or {}),
        })

    def classify_leaf(node, blk, join_ctx=None):
        t = node.text.strip()
        if not t or NOT_LEAF.match(t):
            unresolved.append({'raw': t[:120], 'reason': 'leaf-unclassified',
                               'block': blk.block_id, 'branch': list(node.branch_ids)})
            return
        parts = eq_parts(t)
        if parts:
            la, lcol, plus1, ra, rcol, plus2 = parts
            add_edge(node, blk, la, lcol, plus1, ra, rcol, plus2, join_ctx)
            return
        # 函数包裹键（X.c1 = F(Y.c2) / F(X.c1) = Y.c2）：独立表达，不降级不丢弃
        for fm in (FUNC_EQ_A.match(t), FUNC_EQ_B.match(t)):
            if fm:
                if fm.re is FUNC_EQ_A:
                    la, lcol, plus1, func, ra, rcol, plus2 = fm.groups()
                else:
                    func, la, lcol, plus1, ra, rcol, plus2 = fm.groups()
                add_edge(node, blk, la.upper(), lcol.upper(), plus1, ra.upper(), rcol.upper(), plus2,
                         join_ctx, edge_extra={'func': func.upper(), 'func_wrapped': True})
                return
        # 显式 JOIN 的 ON 中裸列等值（ON cola=colb，无别名限定）：
        # 按 ON 书写顺序定向并打不确定标记，不猜语义（T08 原则的宽松兜底）
        if join_ctx is not None:
            mb = BARE_EQ_LEAF.match(t)
            if mb:
                by_inst = {r.instance_id: r for r in blk.refs}
                lr, rr = by_inst.get(join_ctx['from']), by_inst.get(join_ctx['to'])
                if lr and rr:
                    edges.append({
                        'block': blk.block_id, 'branch': list(node.branch_ids),
                        'l_instance': lr.instance_id, 'l_table': lr.table, 'l_kind': lr.kind,
                        'l_alias': lr.alias, 'l_col': mb.group(1).upper(),
                        'r_instance': rr.instance_id, 'r_table': rr.table, 'r_kind': rr.kind,
                        'r_alias': rr.alias, 'r_col': mb.group(3).upper(),
                        'plus_side': 'L' if mb.group(2) else ('R' if mb.group(4) else None),
                        'and_group': group_of.get(id(node)),
                        'raw': t, 'source': 'on', 'join_type': join_ctx['join_type'],
                        'orientation_uncertain': True,
                    })
                    return
        m = CONST_LEAF.match(t)
        if m:
            col, op, val = m.group(1), m.group(2).upper(), m.group(3)
            if col.upper() not in RESERVED_ALIAS:
                filters.append({'block': blk.block_id, 'branch': list(node.branch_ids),
                                'col': col.upper(), 'op': op, 'val_kind': _val_kind(val),
                                'raw': t[:120]})
                return
        unresolved.append({'raw': t[:120], 'reason': 'leaf-unclassified',
                           'block': blk.block_id, 'branch': list(node.branch_ids)})

    group_of = {}   # id(leaf) -> 'block:prefix gi'：复合键合并范围=同一 AND 节点

    def index_groups(node, bid, prefix):
        for gi, grp in enumerate(node.and_groups()):
            for leaf in grp:
                group_of[id(leaf)] = f'{bid}:{prefix}{gi}'

    def walk(bid):
        blk = p.blocks[bid]
        for ji, j in enumerate(blk.joins):
            if j['on_node'] is not None:
                index_groups(j['on_node'], bid, f'on{ji}:')
        if blk.where_node is not None:
            index_groups(blk.where_node, bid, 'w:')
        for j in blk.joins:
            if j['on_node'] is not None:
                for leaf in j['on_node'].leaves():
                    classify_leaf(leaf, blk, j)
        if blk.where_node is not None:
            for leaf in blk.where_node.leaves():
                classify_leaf(leaf, blk)
        for child in blk.children:
            walk(child)

    walk(top)
    # UNION 其余各臂与游离顶层块同样遍历（各臂 parent=None 或共享父）
    for bid, b in p.blocks.items():
        if b.parent is None and bid != top:
            walk(bid)
    return {
        'blocks': {bid: {
            'block_id': b.block_id, 'parent': b.parent, 'kind': b.kind,
            'refs': [{'instance': r.instance_id, 'table': r.table, 'alias': r.alias,
                      'kind': r.kind, 'sub_block': r.sub_block, 'cte': r.cte_name}
                     for r in b.refs],
            'joins': [{'from': j['from'], 'to': j['to'], 'join_type': j['join_type'],
                       'on': j['on_text'][:200]} for j in b.joins],
            'where': b.where_text[:400],
        } for bid, b in p.blocks.items()},
        'cte_defs': p.cte_defs,
        'edges': edges,
        'unresolved': unresolved,
        'filters': filters,
        'warnings': p.warnings,
    }


def _val_kind(v: str) -> str:
    if v == '?':
        return 'bind'
    if v and v[0] in '\'"':
        return 'str'
    if re.fullmatch(r'\d+(\.\d+)?', v):
        return 'num'
    return 'ident'


def physical_tables(result: dict, max_depth: int = 8) -> dict:
    """instance -> set of underlying physical tables（CTE/派生表递归溯源）."""
    blocks = result['blocks']
    inst_info = {r['instance']: (r, bid) for bid, b in blocks.items() for r in b['refs']}
    phys: dict[int, set] = {}

    def resolve_inst(inst, depth):
        if inst in phys:
            return phys[inst]
        if depth > max_depth:
            return set()
        info = inst_info.get(inst)
        if info is None:
            return set()
        r, bid = info
        if r['kind'] in ('table', 'dblink'):
            phys[inst] = {r['table']}
        else:
            sub = r['sub_block']
            acc = set()
            if sub and sub in blocks:
                for rr in blocks[sub]['refs']:
                    acc |= resolve_inst(rr['instance'], depth + 1)
            phys[inst] = acc
        return phys[inst]

    for inst in inst_info:
        resolve_inst(inst, 0)
    return phys


if __name__ == '__main__':
    import json as _json
    import sys as _sys
    print(_json.dumps(parse_sql(_sys.stdin.read()), ensure_ascii=False, indent=1))

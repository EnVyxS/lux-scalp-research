"""
[P1] Deteksi pola klasik + trendline (MURNI, tanpa I/O -> gampang di-unit-test).

Semua fungsi menerima input primitif (list pivot (index, price), list candle yang
punya .open/.high/.low/.close/.volume, index sekarang, ATR) dan mengembalikan
deskriptor sinyal dict atau None. TIDAK ada dependency ke strategy/engine (hindari
import melingkar).

Deskriptor sinyal (dict):
  {
    "side":  "LONG" | "SHORT",
    "source": "TRENDLINE_BREAK" | "TRENDLINE_BOUNCE" | "DOUBLE_TOP" |
              "DOUBLE_BOTTOM" | "HEAD_SHOULDERS" | "INV_HEAD_SHOULDERS" | "FLAG",
    "level": float,          # level acuan (neckline / trendline / breakout)
    "allow_market": bool,    # True utk breakout (boleh market order jika terkonfirmasi)
    "pattern": str,          # nama pola utk log
  }

Filosofi konfirmasi (dipakai engine/strategy, bukan di sini): breakout WAJIB
konfirmasi = close tegas di luar level + ekspansi volume, ATAU momentum kuat
(displacement besar + lonjakan volume) untuk kasus "harga bergerak dalam".
"""
from typing import List, Optional, Tuple, Dict


# ---------------------------------------------------------------------------
# [P3] HTF pattern context (untuk confluence weighting + extended TP target)
# ---------------------------------------------------------------------------
class _Row:
    """Bungkus baris OHLCV [ts,o,h,l,c,v] agar kompatibel dgn detektor (.high dst)."""
    __slots__ = ("open", "high", "low", "close", "volume")

    def __init__(self, r):
        self.open = r[1]; self.high = r[2]; self.low = r[3]; self.close = r[4]
        self.volume = r[5] if len(r) > 5 else 0.0


def pivots_from_ohlcv(ohlcv, swing_len=3):
    """Deteksi pivot high/low dari list OHLCV. Return (pivot_highs, pivot_lows) as [(idx, price)]."""
    n = len(ohlcv)
    highs = [r[2] for r in ohlcv]
    lows = [r[3] for r in ohlcv]
    ph, pl = [], []
    for i in range(swing_len, n - swing_len):
        if highs[i] == max(highs[i - swing_len:i + swing_len + 1]):
            ph.append((i, highs[i]))
        if lows[i] == min(lows[i - swing_len:i + swing_len + 1]):
            pl.append((i, lows[i]))
    return ph, pl


def _atr_from_ohlcv(ohlcv, period=14):
    if len(ohlcv) < 2:
        return 0.0
    trs = []
    for i in range(1, min(period + 1, len(ohlcv))):
        c = ohlcv[-i]; prev = ohlcv[-(i + 1)]
        trs.append(max(c[2] - c[3], abs(c[2] - prev[4]), abs(c[3] - prev[4])))
    return sum(trs) / len(trs) if trs else 0.0


def adx_from_ohlcv(ohlcv, n=14):
    """[REGIME] Wilder ADX dari list OHLCV [ts,o,h,l,c,v]. Return nilai ADX terakhir
    (0.0 kalau data kurang). Dipakai sbg pengukur kekuatan tren (regime filter)."""
    m = len(ohlcv)
    if m < 2 * n + 2:
        return 0.0
    highs = [r[2] for r in ohlcv]; lows = [r[3] for r in ohlcv]; closes = [r[4] for r in ohlcv]
    trs = []; pdm = []; mdm = []
    for i in range(1, m):
        up = highs[i] - highs[i - 1]; dn = lows[i - 1] - lows[i]
        pdm.append(up if (up > dn and up > 0) else 0.0)
        mdm.append(dn if (dn > up and dn > 0) else 0.0)
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    if len(trs) < n:
        return 0.0
    def _wilder(arr):
        s = sum(arr[:n]); out = [s]
        for i in range(n, len(arr)):
            s = s - s / n + arr[i]; out.append(s)
        return out
    atr_s = _wilder(trs); pdm_s = _wilder(pdm); mdm_s = _wilder(mdm)
    dxs = []
    for a, p, mm in zip(atr_s, pdm_s, mdm_s):
        if a <= 0:
            dxs.append(0.0); continue
        pdi = 100 * p / a; mdi = 100 * mm / a
        tot = pdi + mdi
        dxs.append(100 * abs(pdi - mdi) / tot if tot > 0 else 0.0)
    if len(dxs) < n:
        return dxs[-1] if dxs else 0.0
    adx = sum(dxs[:n]) / n
    for i in range(n, len(dxs)):
        adx = (adx * (n - 1) + dxs[i]) / n
    return adx


def htf_context(ohlcv, swing_len=3, *, tol_atr=0.5, tl_tol_atr=0.6,
                target_lookback_pivots=6):
    """
    [P3] Deteksi KONTEKS pola di satu HTF dari OHLCV (murni). Dipakai untuk
    confluence weighting + target TP extended. Return dict:
      {"side", "source", "pattern", "level", "target"} atau None.
    `target` = ekstrem swing HTF searah (LONG=pivot high tertinggi terakhir,
    SHORT=pivot low terendah) sebagai magnet TP skala-HTF.
    """
    if not ohlcv or len(ohlcv) < 10:
        return None
    closed = ohlcv[:-1]  # buang candle yang masih berjalan
    atr = _atr_from_ohlcv(closed)
    if atr <= 0:
        return None
    ph, pl = pivots_from_ohlcv(closed, swing_len)
    candles = [_Row(r) for r in closed]
    cur = len(closed) - 1
    ctxs = [
        detect_double_top(ph, pl, candles, atr, tol_atr=tol_atr),
        detect_double_bottom(ph, pl, candles, atr, tol_atr=tol_atr),
        detect_head_shoulders(ph, pl, candles, atr),
        detect_inv_head_shoulders(ph, pl, candles, atr),
        detect_triple_top(ph, pl, candles, atr, tol_atr=tol_atr),
        detect_triple_bottom(ph, pl, candles, atr, tol_atr=tol_atr),
        detect_triangle(ph, pl, candles, cur, atr, tol_atr=tl_tol_atr),
        detect_rectangle(ph, pl, candles, cur, atr, tol_atr=tl_tol_atr),
        detect_wedge(ph, pl, candles, cur, atr, tol_atr=tl_tol_atr),
        detect_complex_head_shoulders(ph, pl, candles, atr),
        detect_complex_inv_head_shoulders(ph, pl, candles, atr),
        detect_trendline_break(ph, pl, candles, cur, atr, tol_atr=tl_tol_atr),
    ]
    for ctx in ctxs:
        if ctx is None:
            continue
        # target = ekstrem swing HTF searah (magnet TP skala HTF)
        if ctx["side"] == "LONG" and ph:
            ctx["target"] = max(p for _, p in ph[-target_lookback_pivots:])
        elif ctx["side"] == "SHORT" and pl:
            ctx["target"] = min(p for _, p in pl[-target_lookback_pivots:])
        else:
            ctx["target"] = 0.0
        return ctx
    return None


# ---------------------------------------------------------------------------
# Helper garis (least-squares) + volume
# ---------------------------------------------------------------------------
def linfit(points: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    """Least-squares fit -> (slope, intercept). None kalau < 2 titik / degenerate."""
    n = len(points)
    if n < 2:
        return None
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sxx = sum(p[0] * p[0] for p in points)
    sxy = sum(p[0] * p[1] for p in points)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def project(line: Tuple[float, float], x: float) -> float:
    slope, intercept = line
    return slope * x + intercept


def avg_volume(candles, lookback: int = 20) -> float:
    """Rata-rata volume `lookback` candle SEBELUM candle terakhir."""
    if len(candles) < 2:
        return 0.0
    prev = candles[-(lookback + 1):-1]
    vols = [getattr(c, "volume", 0.0) or 0.0 for c in prev]
    vols = [v for v in vols if v > 0]
    return (sum(vols) / len(vols)) if vols else 0.0


def volume_expansion(candles, k: float = 1.5, lookback: int = 20) -> bool:
    """True kalau volume candle terakhir >= k x rata-rata volume sebelumnya.
    Kalau data volume tak ada (semua 0) -> return True (jangan salah-blokir;
    volume 0 berarti feed tak menyediakan volume, bukan berarti volume rendah)."""
    if len(candles) < 3:
        return False
    last = getattr(candles[-1], "volume", 0.0) or 0.0
    base = avg_volume(candles, lookback)
    if base <= 0:
        return True   # volume tak tersedia -> lewati filter volume
    return last >= k * base


def decisive_close_beyond(candle, level: float, side: str, atr: float,
                          buf_atr: float = 0.1) -> bool:
    """Close 'tegas' di luar level: LONG close > level+buf; SHORT close < level-buf."""
    buf = max(atr * buf_atr, 0.0)
    if side == "LONG":
        return candle.close > level + buf
    return candle.close < level - buf


def strong_displacement(candle, atr: float, body_atr: float = 1.0) -> bool:
    """Candle displacement besar (body >= body_atr x ATR) searah close-open.
    Dipakai sbg jalur 'momentum' utk kasus 'harga bergerak dalam' tanpa perlu
    menunggu close super tegas di atas buffer."""
    if atr <= 0:
        return False
    return abs(candle.close - candle.open) >= body_atr * atr


def confirm_breakout(candles, level: float, side: str, atr: float, *,
                     buf_atr: float = 0.1, vol_k: float = 1.5, vol_lookback: int = 20,
                     momentum_body_atr: float = 1.2) -> bool:
    """
    Konfirmasi breakout (dipakai sebelum market order):
      JALUR A (standar): close tegas di luar level + ekspansi volume.
      JALUR B (momentum): displacement besar (body >= momentum_body_atr x ATR)
                          + ekspansi volume -> untuk 'harga bergerak dalam' cepat,
                          walau close belum jauh dari level.
    Keduanya WAJIB ekspansi volume (atau volume tak tersedia).
    """
    if not candles:
        return False
    c = candles[-1]
    vol_ok = volume_expansion(candles, vol_k, vol_lookback)
    if not vol_ok:
        return False
    if decisive_close_beyond(c, level, side, atr, buf_atr):
        return True
    # Jalur momentum: candle dorongan besar searah break
    if strong_displacement(c, atr, momentum_body_atr):
        if side == "LONG" and c.close > level:
            return True
        if side == "SHORT" and c.close < level:
            return True
    return False


# ---------------------------------------------------------------------------
# Trendline (garis manual pivot-to-pivot)
# ---------------------------------------------------------------------------
def detect_trendline(pivots: List[Tuple[int, float]], kind: str, atr: float, *,
                     lookback: int = 5, min_points: int = 3,
                     tol_atr: float = 0.6) -> Optional[Tuple[float, float]]:
    """
    Fit trendline dari pivot terakhir. kind='res' (dari pivot highs, resistance)
    atau 'sup' (dari pivot lows, support). Valid kalau >= min_points pivot
    'menyentuh' garis dalam toleransi tol_atr x ATR.
    Return (slope, intercept) atau None.
    """
    if atr <= 0 or len(pivots) < min_points:
        return None
    pts = pivots[-lookback:]
    if len(pts) < min_points:
        return None
    line = linfit([(float(i), float(p)) for i, p in pts])
    if line is None:
        return None
    tol = tol_atr * atr
    touches = sum(1 for i, p in pts if abs(p - project(line, i)) <= tol)
    if touches < min_points:
        return None
    return line


def detect_trendline_break(pivot_highs, pivot_lows, candles, cur_index, atr, *,
                           lookback=5, min_points=3, tol_atr=0.6,
                           buf_atr=0.1) -> Optional[Dict]:
    """Breakout menembus trendline: LONG tembus resistance turun, SHORT tembus support naik.
    Hanya deteksi geometris; konfirmasi volume dilakukan pemanggil (confirm_breakout)."""
    if not candles:
        return None
    c = candles[-1]
    # LONG: tembus ke ATAS resistance (dari pivot highs)
    res = detect_trendline(pivot_highs, "res", atr, lookback=lookback,
                           min_points=min_points, tol_atr=tol_atr)
    if res is not None:
        lvl = project(res, cur_index)
        if decisive_close_beyond(c, lvl, "LONG", atr, buf_atr):
            return {"side": "LONG", "source": "TRENDLINE_BREAK", "level": lvl,
                    "allow_market": True, "pattern": "trendline-break-up"}
    # SHORT: tembus ke BAWAH support (dari pivot lows)
    sup = detect_trendline(pivot_lows, "sup", atr, lookback=lookback,
                           min_points=min_points, tol_atr=tol_atr)
    if sup is not None:
        lvl = project(sup, cur_index)
        if decisive_close_beyond(c, lvl, "SHORT", atr, buf_atr):
            return {"side": "SHORT", "source": "TRENDLINE_BREAK", "level": lvl,
                    "allow_market": True, "pattern": "trendline-break-down"}
    return None


def detect_trendline_bounce(pivot_highs, pivot_lows, candles, cur_index, atr, *,
                            lookback=5, min_points=3, tol_atr=0.6,
                            touch_atr=0.5) -> Optional[Dict]:
    """Pantulan di trendline: LONG memantul dari support naik; SHORT dari resistance turun.
    Wick menyentuh garis lalu close kembali di sisi yang benar (rejection)."""
    if not candles:
        return None
    c = candles[-1]
    touch = touch_atr * atr
    # LONG bounce dari support (pivot lows)
    sup = detect_trendline(pivot_lows, "sup", atr, lookback=lookback,
                           min_points=min_points, tol_atr=tol_atr)
    if sup is not None:
        lvl = project(sup, cur_index)
        if c.low <= lvl + touch and c.close > lvl:
            return {"side": "LONG", "source": "TRENDLINE_BOUNCE", "level": lvl,
                    "allow_market": False, "pattern": "trendline-bounce-support"}
    # SHORT bounce dari resistance (pivot highs)
    res = detect_trendline(pivot_highs, "res", atr, lookback=lookback,
                           min_points=min_points, tol_atr=tol_atr)
    if res is not None:
        lvl = project(res, cur_index)
        if c.high >= lvl - touch and c.close < lvl:
            return {"side": "SHORT", "source": "TRENDLINE_BOUNCE", "level": lvl,
                    "allow_market": False, "pattern": "trendline-bounce-resistance"}
    return None


# ---------------------------------------------------------------------------
# Double Top / Double Bottom (neckline break)
# ---------------------------------------------------------------------------
def detect_double_top(pivot_highs, pivot_lows, candles, atr, *,
                      tol_atr=0.5) -> Optional[Dict]:
    """Double top (M): dua pivot high terakhir ~sama (dalam tol), dgn trough di
    antara = neckline. Konfirmasi saat close < neckline (break bawah)."""
    if atr <= 0 or len(pivot_highs) < 2 or not pivot_lows or not candles:
        return None
    (i1, p1), (i2, p2) = pivot_highs[-2], pivot_highs[-1]
    if abs(p1 - p2) > tol_atr * atr:
        return None
    # trough (neckline) = pivot low terendah di antara dua puncak
    between = [pl for pl in pivot_lows if i1 <= pl[0] <= i2]
    if not between:
        return None
    neckline = min(p for _, p in between)
    c = candles[-1]
    if c.close < neckline:
        return {"side": "SHORT", "source": "DOUBLE_TOP", "level": neckline,
                "allow_market": True, "pattern": "double-top"}
    return None


def detect_double_bottom(pivot_highs, pivot_lows, candles, atr, *,
                         tol_atr=0.5) -> Optional[Dict]:
    """Double bottom (W): dua pivot low terakhir ~sama, neckline = peak di antara.
    Konfirmasi saat close > neckline (break atas)."""
    if atr <= 0 or len(pivot_lows) < 2 or not pivot_highs or not candles:
        return None
    (i1, p1), (i2, p2) = pivot_lows[-2], pivot_lows[-1]
    if abs(p1 - p2) > tol_atr * atr:
        return None
    between = [ph for ph in pivot_highs if i1 <= ph[0] <= i2]
    if not between:
        return None
    neckline = max(p for _, p in between)
    c = candles[-1]
    if c.close > neckline:
        return {"side": "LONG", "source": "DOUBLE_BOTTOM", "level": neckline,
                "allow_market": True, "pattern": "double-bottom"}
    return None


# ---------------------------------------------------------------------------
# Head & Shoulders (top) + Inverse (bottom)
# ---------------------------------------------------------------------------
def detect_head_shoulders(pivot_highs, pivot_lows, candles, atr, *,
                          shoulder_tol_atr=0.7, head_min_atr=0.3) -> Optional[Dict]:
    """H&S top: 3 pivot high terakhir L,H,R dgn H tertinggi & L~R (dalam tol).
    Neckline = garis dua trough di antara bahu-kepala; konfirmasi close < neckline."""
    if atr <= 0 or len(pivot_highs) < 3 or len(pivot_lows) < 2 or not candles:
        return None
    (li, lp), (hi, hp), (ri, rp) = pivot_highs[-3], pivot_highs[-2], pivot_highs[-1]
    if not (hp > lp and hp > rp):
        return None
    if hp - max(lp, rp) < head_min_atr * atr:
        return None
    if abs(lp - rp) > shoulder_tol_atr * atr:
        return None
    troughs = [pl for pl in pivot_lows if li <= pl[0] <= ri]
    if len(troughs) < 2:
        return None
    line = linfit([(float(i), float(p)) for i, p in troughs[-2:]])
    if line is None:
        return None
    c = candles[-1]
    neckline = project(line, troughs[-1][0])
    if c.close < neckline:
        return {"side": "SHORT", "source": "HEAD_SHOULDERS", "level": neckline,
                "allow_market": True, "pattern": "head-shoulders-top"}
    return None


def detect_inv_head_shoulders(pivot_highs, pivot_lows, candles, atr, *,
                              shoulder_tol_atr=0.7, head_min_atr=0.3) -> Optional[Dict]:
    """Inverse H&S (bottom): 3 pivot low terakhir dgn kepala terendah & bahu ~sama.
    Neckline = dua peak; konfirmasi close > neckline."""
    if atr <= 0 or len(pivot_lows) < 3 or len(pivot_highs) < 2 or not candles:
        return None
    (li, lp), (hi, hp), (ri, rp) = pivot_lows[-3], pivot_lows[-2], pivot_lows[-1]
    if not (hp < lp and hp < rp):
        return None
    if min(lp, rp) - hp < head_min_atr * atr:
        return None
    if abs(lp - rp) > shoulder_tol_atr * atr:
        return None
    peaks = [ph for ph in pivot_highs if li <= ph[0] <= ri]
    if len(peaks) < 2:
        return None
    line = linfit([(float(i), float(p)) for i, p in peaks[-2:]])
    if line is None:
        return None
    neckline = project(line, peaks[-1][0])
    c = candles[-1]
    if c.close > neckline:
        return {"side": "LONG", "source": "INV_HEAD_SHOULDERS", "level": neckline,
                "allow_market": True, "pattern": "inv-head-shoulders"}
    return None


# ---------------------------------------------------------------------------
# Flag / continuation (konsolidasi setelah impuls)
# ---------------------------------------------------------------------------
def detect_flag(candles, atr, *, impulse_lookback=12, impulse_atr=3.0,
                consol_bars=6, consol_max_atr=1.5) -> Optional[Dict]:
    """Flag: impuls kuat (>= impulse_atr x ATR dlm impulse_lookback bar) lalu
    konsolidasi sempit (range <= consol_max_atr x ATR selama consol_bars bar),
    lalu breakout searah impuls (close keluar range konsolidasi)."""
    if atr <= 0 or len(candles) < impulse_lookback + consol_bars + 1:
        return None
    consol = candles[-(consol_bars + 1):-1]
    if len(consol) < consol_bars:
        return None
    hi = max(c.high for c in consol)
    lo = min(c.low for c in consol)
    if (hi - lo) > consol_max_atr * atr:
        return None   # konsolidasi tidak cukup sempit
    # ukur impuls sebelum konsolidasi
    pre = candles[-(impulse_lookback + consol_bars + 1):-(consol_bars + 1)]
    if len(pre) < 3:
        return None
    move = pre[-1].close - pre[0].close
    if abs(move) < impulse_atr * atr:
        return None
    c = candles[-1]
    # [P1b] Entry FLAG di OB (bukan kejar breakout market): allow_market=False ->
    # engine masuk LIMIT di tepi OB (LONG=OB bawah/demand, SHORT=OB atas/supply).
    # Lebih baik R:R & anti-fakeout untuk continuation; _build_pattern_signal
    # yang memilih OB searah.
    if move > 0 and c.close > hi:
        return {"side": "LONG", "source": "FLAG", "level": hi,
                "allow_market": False, "pattern": "bull-flag"}
    if move < 0 and c.close < lo:
        return {"side": "SHORT", "source": "FLAG", "level": lo,
                "allow_market": False, "pattern": "bear-flag"}
    return None


# ---------------------------------------------------------------------------
# [P2] Triangle / Rectangle / Wedge (dari sepasang trendline res+sup)
# ---------------------------------------------------------------------------
def _slope_class(slope: float, span: float, atr: float, flat_tol_atr: float = 0.5) -> str:
    """Klasifikasi arah garis: 'up' / 'down' / 'flat' (deadband flat_tol_atr x ATR)."""
    delta = slope * (span or 1)
    tol = flat_tol_atr * atr
    if delta > tol:
        return "up"
    if delta < -tol:
        return "down"
    return "flat"


def _res_sup(pivot_highs, pivot_lows, atr, lookback, min_points, tol_atr):
    res = detect_trendline(pivot_highs, "res", atr, lookback=lookback,
                           min_points=min_points, tol_atr=tol_atr)
    sup = detect_trendline(pivot_lows, "sup", atr, lookback=lookback,
                           min_points=min_points, tol_atr=tol_atr)
    return res, sup


def detect_triangle(pivot_highs, pivot_lows, candles, cur_index, atr, *,
                    lookback=6, min_points=3, tol_atr=0.6, buf_atr=0.1,
                    flat_tol_atr=0.5) -> Optional[Dict]:
    """Ascending (res flat + sup naik -> break up), Descending (sup flat + res turun
    -> break down), Symmetrical (res turun & sup naik, konvergen -> ikut arah break)."""
    if atr <= 0 or not candles:
        return None
    if len(pivot_highs) < min_points or len(pivot_lows) < min_points:
        return None
    res, sup = _res_sup(pivot_highs, pivot_lows, atr, lookback, min_points, tol_atr)
    if res is None or sup is None:
        return None
    ph = pivot_highs[-lookback:]
    pl = pivot_lows[-lookback:]
    span_h = ph[-1][0] - ph[0][0]
    span_l = pl[-1][0] - pl[0][0]
    rcls = _slope_class(res[0], span_h, atr, flat_tol_atr)
    scls = _slope_class(sup[0], span_l, atr, flat_tol_atr)
    c = candles[-1]
    rlvl = project(res, cur_index)
    slvl = project(sup, cur_index)
    if rcls == "flat" and scls == "up" and decisive_close_beyond(c, rlvl, "LONG", atr, buf_atr):
        return {"side": "LONG", "source": "TRIANGLE_ASC", "level": rlvl,
                "allow_market": True, "pattern": "ascending-triangle"}
    if scls == "flat" and rcls == "down" and decisive_close_beyond(c, slvl, "SHORT", atr, buf_atr):
        return {"side": "SHORT", "source": "TRIANGLE_DESC", "level": slvl,
                "allow_market": True, "pattern": "descending-triangle"}
    if rcls == "down" and scls == "up":
        if decisive_close_beyond(c, rlvl, "LONG", atr, buf_atr):
            return {"side": "LONG", "source": "TRIANGLE_SYM", "level": rlvl,
                    "allow_market": True, "pattern": "symmetrical-triangle-up"}
        if decisive_close_beyond(c, slvl, "SHORT", atr, buf_atr):
            return {"side": "SHORT", "source": "TRIANGLE_SYM", "level": slvl,
                    "allow_market": True, "pattern": "symmetrical-triangle-down"}
    return None


def detect_rectangle(pivot_highs, pivot_lows, candles, cur_index, atr, *,
                     lookback=6, min_points=3, tol_atr=0.6, buf_atr=0.1,
                     flat_tol_atr=0.5) -> Optional[Dict]:
    """Rectangle/range: res flat + sup flat. Break atas -> LONG, break bawah -> SHORT."""
    if atr <= 0 or not candles:
        return None
    if len(pivot_highs) < min_points or len(pivot_lows) < min_points:
        return None
    res, sup = _res_sup(pivot_highs, pivot_lows, atr, lookback, min_points, tol_atr)
    if res is None or sup is None:
        return None
    ph = pivot_highs[-lookback:]
    pl = pivot_lows[-lookback:]
    rcls = _slope_class(res[0], ph[-1][0] - ph[0][0], atr, flat_tol_atr)
    scls = _slope_class(sup[0], pl[-1][0] - pl[0][0], atr, flat_tol_atr)
    if rcls != "flat" or scls != "flat":
        return None
    c = candles[-1]
    rlvl = project(res, cur_index)
    slvl = project(sup, cur_index)
    if decisive_close_beyond(c, rlvl, "LONG", atr, buf_atr):
        return {"side": "LONG", "source": "RECTANGLE", "level": rlvl,
                "allow_market": True, "pattern": "rectangle-break-up"}
    if decisive_close_beyond(c, slvl, "SHORT", atr, buf_atr):
        return {"side": "SHORT", "source": "RECTANGLE", "level": slvl,
                "allow_market": True, "pattern": "rectangle-break-down"}
    return None


def detect_wedge(pivot_highs, pivot_lows, candles, cur_index, atr, *,
                 lookback=6, min_points=3, tol_atr=0.6, buf_atr=0.1) -> Optional[Dict]:
    """Rising wedge (bearish): res & sup naik, konvergen (sup lebih curam) -> break
    bawah support. Falling wedge (bullish): res & sup turun, konvergen (res lebih
    curam turun) -> break atas resistance."""
    if atr <= 0 or not candles:
        return None
    if len(pivot_highs) < min_points or len(pivot_lows) < min_points:
        return None
    res, sup = _res_sup(pivot_highs, pivot_lows, atr, lookback, min_points, tol_atr)
    if res is None or sup is None:
        return None
    rs, ss = res[0], sup[0]
    c = candles[-1]
    rlvl = project(res, cur_index)
    slvl = project(sup, cur_index)
    # rising wedge: keduanya positif, support naik lebih cepat (konvergen ke atas)
    if rs > 0 and ss > 0 and ss > rs and decisive_close_beyond(c, slvl, "SHORT", atr, buf_atr):
        return {"side": "SHORT", "source": "WEDGE_RISING", "level": slvl,
                "allow_market": True, "pattern": "rising-wedge"}
    # falling wedge: keduanya negatif, resistance turun lebih cepat (konvergen ke bawah)
    if rs < 0 and ss < 0 and rs < ss and decisive_close_beyond(c, rlvl, "LONG", atr, buf_atr):
        return {"side": "LONG", "source": "WEDGE_FALLING", "level": rlvl,
                "allow_market": True, "pattern": "falling-wedge"}
    return None


# ---------------------------------------------------------------------------
# [P2] Triple top / bottom + Complex H&S
# ---------------------------------------------------------------------------
def detect_triple_top(pivot_highs, pivot_lows, candles, atr, *, tol_atr=0.5) -> Optional[Dict]:
    if atr <= 0 or len(pivot_highs) < 3 or not pivot_lows or not candles:
        return None
    (i1, p1), (i2, p2), (i3, p3) = pivot_highs[-3:]
    if max(abs(p1 - p2), abs(p2 - p3), abs(p1 - p3)) > tol_atr * atr:
        return None
    between = [pl for pl in pivot_lows if i1 <= pl[0] <= i3]
    if not between:
        return None
    neckline = min(p for _, p in between)
    if candles[-1].close < neckline:
        return {"side": "SHORT", "source": "TRIPLE_TOP", "level": neckline,
                "allow_market": True, "pattern": "triple-top"}
    return None


def detect_triple_bottom(pivot_highs, pivot_lows, candles, atr, *, tol_atr=0.5) -> Optional[Dict]:
    if atr <= 0 or len(pivot_lows) < 3 or not pivot_highs or not candles:
        return None
    (i1, p1), (i2, p2), (i3, p3) = pivot_lows[-3:]
    if max(abs(p1 - p2), abs(p2 - p3), abs(p1 - p3)) > tol_atr * atr:
        return None
    between = [ph for ph in pivot_highs if i1 <= ph[0] <= i3]
    if not between:
        return None
    neckline = max(p for _, p in between)
    if candles[-1].close > neckline:
        return {"side": "LONG", "source": "TRIPLE_BOTTOM", "level": neckline,
                "allow_market": True, "pattern": "triple-bottom"}
    return None


def detect_complex_head_shoulders(pivot_highs, pivot_lows, candles, atr, *,
                                  shoulder_tol_atr=0.8, head_min_atr=0.3,
                                  lookback=7) -> Optional[Dict]:
    """Complex H&S top: dari `lookback` pivot high terakhir, kepala=tertinggi dgn
    bahu di KEDUA sisi (boleh banyak), bahu kiri~kanan (rata-rata), kepala > bahu.
    Neckline via dua trough; konfirmasi close < neckline."""
    if atr <= 0 or len(pivot_highs) < 4 or len(pivot_lows) < 2 or not candles:
        return None
    phs = pivot_highs[-lookback:]
    head_k = max(range(len(phs)), key=lambda k: phs[k][1])
    if head_k == 0 or head_k == len(phs) - 1:
        return None
    head = phs[head_k][1]
    left = [phs[k][1] for k in range(head_k)]
    right = [phs[k][1] for k in range(head_k + 1, len(phs))]
    if head - max(max(left), max(right)) < head_min_atr * atr:
        return None
    if abs(sum(left) / len(left) - sum(right) / len(right)) > shoulder_tol_atr * atr:
        return None
    troughs = [pl for pl in pivot_lows if phs[0][0] <= pl[0] <= phs[-1][0]]
    if len(troughs) < 2:
        return None
    line = linfit([(float(i), float(p)) for i, p in troughs[-2:]])
    if line is None:
        return None
    neckline = project(line, troughs[-1][0])
    if candles[-1].close < neckline:
        return {"side": "SHORT", "source": "COMPLEX_HS", "level": neckline,
                "allow_market": True, "pattern": "complex-head-shoulders"}
    return None


def detect_complex_inv_head_shoulders(pivot_highs, pivot_lows, candles, atr, *,
                                      shoulder_tol_atr=0.8, head_min_atr=0.3,
                                      lookback=7) -> Optional[Dict]:
    """Complex Inverse H&S bottom (cermin complex H&S top)."""
    if atr <= 0 or len(pivot_lows) < 4 or len(pivot_highs) < 2 or not candles:
        return None
    pls = pivot_lows[-lookback:]
    head_k = min(range(len(pls)), key=lambda k: pls[k][1])
    if head_k == 0 or head_k == len(pls) - 1:
        return None
    head = pls[head_k][1]
    left = [pls[k][1] for k in range(head_k)]
    right = [pls[k][1] for k in range(head_k + 1, len(pls))]
    if min(min(left), min(right)) - head < head_min_atr * atr:
        return None
    if abs(sum(left) / len(left) - sum(right) / len(right)) > shoulder_tol_atr * atr:
        return None
    peaks = [ph for ph in pivot_highs if pls[0][0] <= ph[0] <= pls[-1][0]]
    if len(peaks) < 2:
        return None
    line = linfit([(float(i), float(p)) for i, p in peaks[-2:]])
    if line is None:
        return None
    neckline = project(line, peaks[-1][0])
    if candles[-1].close > neckline:
        return {"side": "LONG", "source": "COMPLEX_IHS", "level": neckline,
                "allow_market": True, "pattern": "complex-inv-head-shoulders"}
    return None


def adx_di_from_ohlcv(ohlcv, n=14):
    """[DI-ALIGN] Wilder ADX + Directional Indicators dari OHLCV [ts,o,h,l,c,v].
    Return (adx, pdi, mdi):
      adx = Average Directional Index (kekuatan tren, 0-100)
      pdi = +DI  (positive directional indicator, bull pressure)
      mdi = -DI  (minus directional indicator, bear pressure)
    Return (0.0, 0.0, 0.0) kalau data kurang.
    Dipakai sbg gate arah trend sebelum izinkan TRENDLINE_BREAK entry:
      LONG break valid hanya kalau pdi > mdi (tren naik)
      SHORT break valid hanya kalau mdi > pdi (tren turun)
    """
    m = len(ohlcv)
    if m < 2 * n + 2:
        return 0.0, 0.0, 0.0
    highs = [r[2] for r in ohlcv]
    lows  = [r[3] for r in ohlcv]
    closes = [r[4] for r in ohlcv]
    trs = []; pdm = []; mdm = []
    for i in range(1, m):
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        pdm.append(up if (up > dn and up > 0) else 0.0)
        mdm.append(dn if (dn > up and dn > 0) else 0.0)
        trs.append(max(highs[i] - lows[i],
                       abs(highs[i] - closes[i - 1]),
                       abs(lows[i]  - closes[i - 1])))
    if len(trs) < n:
        return 0.0, 0.0, 0.0

    def _wilder(arr):
        s = sum(arr[:n]); out = [s]
        for i in range(n, len(arr)):
            s = s - s / n + arr[i]; out.append(s)
        return out

    atr_s = _wilder(trs)
    pdm_s = _wilder(pdm)
    mdm_s = _wilder(mdm)

    dxs = []
    last_pdi = last_mdi = 0.0
    for a, p, mm in zip(atr_s, pdm_s, mdm_s):
        if a <= 0:
            dxs.append(0.0); continue
        pdi_val = 100 * p / a
        mdi_val = 100 * mm / a
        last_pdi, last_mdi = pdi_val, mdi_val
        tot = pdi_val + mdi_val
        dxs.append(100 * abs(pdi_val - mdi_val) / tot if tot > 0 else 0.0)

    if len(dxs) < n:
        return (dxs[-1] if dxs else 0.0), last_pdi, last_mdi

    adx = sum(dxs[:n]) / n
    for i in range(n, len(dxs)):
        adx = (adx * (n - 1) + dxs[i]) / n
    return adx, last_pdi, last_mdi

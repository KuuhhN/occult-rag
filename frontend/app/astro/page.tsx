"use client";

// 占星择时版块：行星时计算 + 行星状态 + 一键最佳做符时间推荐
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TALISMAN_KINDS = ["爱情", "财富", "保护", "智慧", "幸运", "沟通", "权威", "疗愈", "驱邪"];

type Hour = { start: string; end: string; planet: string; day_night: string };
type PlanetState = { planet: string; sign: string; degree: number; retrograde: boolean; status: string[] };
type Window = { date: string; day_night: string; start: string; end: string; sign: string; retrograde: boolean; status: string[]; day_ruler: string };

export default function AstroPage() {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [city, setCity] = useState("内江");
  const [cities, setCities] = useState<string[]>([]);
  const [kind, setKind] = useState("爱情");
  const [hours, setHours] = useState<Hour[]>([]);
  const [states, setStates] = useState<PlanetState[]>([]);
  const [dayRuler, setDayRuler] = useState("");
  const [sunrise, setSunrise] = useState("");
  const [sunset, setSunset] = useState("");
  const [windows, setWindows] = useState<Window[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadHours = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch(`${API}/planetary-hours?date=${date}&city=${encodeURIComponent(city)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setHours(d.hours || []);
      setStates(d.planet_states || []);
      setDayRuler(d.day_ruler || "");
      setSunrise(d.sunrise || "");
      setSunset(d.sunset || "");
    } catch (e) {
      setError(`加载行星时失败：${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  };

  const loadBestTime = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch(
        `${API}/planetary-hours/best-time?kind=${encodeURIComponent(kind)}&date=${date}&city=${encodeURIComponent(city)}`
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setWindows(d.windows || []);
    } catch (e) {
      setError(`做符推荐失败：${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHours();
    // 加载内置城市表
    fetch(`${API}/planetary-hours/cities`)
      .then((r) => r.json())
      .then((d) => setCities(d.cities || []))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="astro-page">
      <div className="alchemy-header">
        <a href="/" className="back-link">← 返回</a>
        <h1 className="occult-title">🔯 占星择时</h1>
        <p className="subtitle">行星时 · 行星状态 · 一键最佳做符时间 — 天文算法离线计算</p>
      </div>

      <div className="alchemy-filters">
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="alchemy-select"
        />
        <input
          type="text"
          list="city-list"
          value={city}
          onChange={(e) => setCity(e.target.value)}
          placeholder="输入城市名（如：内江 / 成都 / 上海）"
          className="alchemy-select astro-city-input"
        />
        <datalist id="city-list">
          {cities.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>
        <button className="sidebar-btn primary" onClick={loadHours} disabled={loading}>
          计算行星时
        </button>
      </div>

      {error && <p className="tarot-error">{error}</p>}

      {dayRuler && (
        <div className="astro-day-summary">
          <span className="astro-day-ruler">
            本日主宰行星：<strong>{dayRuler}</strong>
          </span>
          <span className="astro-suntime">日出 {sunrise} · 日落 {sunset}（UTC+8）</span>
        </div>
      )}

      {states.length > 0 && (
        <section className="astro-section">
          <h2 className="alchemy-book-title">🪐 行星状态</h2>
          <div className="astro-states">
            {states.map((s) => (
              <div key={s.planet} className={`astro-state ${s.retrograde ? "retro" : ""}`}>
                <span className="astro-state-name">{s.planet}</span>
                <span className="astro-state-sign">{s.sign} {s.degree}°</span>
                <span className="astro-state-status">
                  {s.status.length > 0 ? s.status.join("、") : "普通"}
                  {s.retrograde ? " ⚠️逆行" : ""}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {hours.length > 0 && (
        <section className="astro-section">
          <h2 className="alchemy-book-title">🕰️ 行星时时间表</h2>
          <div className="astro-hours">
            {hours.map((h, i) => (
              <div key={i} className={`astro-hour ${h.day_night}`}>
                <span className="astro-hour-time">{h.start}–{h.end}</span>
                <span className="astro-hour-planet">{h.planet}</span>
                <span className="astro-hour-dn">{h.day_night === "day" ? "白昼" : "夜晚"}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="astro-section">
        <h2 className="alchemy-book-title">🔮 一键最佳做符时间</h2>
        <div className="alchemy-filters">
          <select value={kind} onChange={(e) => setKind(e.target.value)} className="alchemy-select">
            {TALISMAN_KINDS.map((k) => (
              <option key={k} value={k}>{k}符</option>
            ))}
          </select>
          <button className="sidebar-btn primary" onClick={loadBestTime} disabled={loading}>
            推荐最佳时间
          </button>
        </div>
        {windows.length > 0 && (
          <div className="astro-windows">
            {windows.map((w, i) => (
              <div key={i} className={`astro-window ${w.retrograde ? "retro" : "good"}`}>
                <span className="astro-window-rank">{i + 1}</span>
                <span className="astro-window-date">{w.date} {w.day_night === "day" ? "白昼" : "夜晚"}</span>
                <span className="astro-window-time">{w.start}–{w.end}</span>
                <span className="astro-window-sign">{w.sign}</span>
                <span className="astro-window-status">
                  {w.status.length > 0 ? w.status.join("、") : "普通"}
                  {w.retrograde ? " ⚠️逆行" : ""}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

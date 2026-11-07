import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { invoke, convertFileSrc } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import {
  AudioLines,
  FolderOpen,
  Plus,
  Sparkles,
  ShieldCheck,
  Download,
  X,
} from "lucide-react";
import "./voice.css";

type Profile = {
  id: string;
  name: string;
  status: string;
  seconds: number;
  audio: string;
};
type Library = { primary: string | null; profiles: Profile[] };
type Recording = { id: number; timestamp: number };
type AudioResult = { id: string; audio: string; seconds: number };
type Storage = {
  root: string;
  references: string;
  outputs: string;
  dictionary: string;
  runtimeReady: boolean;
  modelReady: boolean;
};
const call = <T,>(action: string, payload: Record<string, unknown> = {}) =>
  invoke<string>("voice_call", {
    action,
    payload: JSON.stringify(payload),
  }).then((raw) => JSON.parse(raw) as T);

export default function VoiceSettings() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<"generate" | "library">("generate");
  const [library, setLibrary] = useState<Library>({
    primary: null,
    profiles: [],
  });
  const [storage, setStorage] = useState<Storage | null>(null);
  const [profile, setProfile] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState("working");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const cancelled = useRef(false);
  const [result, setResult] = useState<AudioResult | null>(null);
  const [history, setHistory] = useState<Recording[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<{
    audio: string;
    text: string;
    path?: string;
  } | null>(null);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [listened, setListened] = useState(false);
  const [comparison, setComparison] = useState<AudioResult | null>(null);
  const [candidateAudio, setCandidateAudio] = useState<AudioResult | null>(
    null,
  );
  const refresh = async () => {
    const l = await call<Library>("list");
    setLibrary(l);
    setProfile((p) =>
      l.profiles.some((x) => x.id === p)
        ? p
        : l.primary || l.profiles[0]?.id || "",
    );
    setStorage(await call<Storage>("storage"));
  };
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    cancelled.current = false;
    try {
      await fn();
    } catch {
      if (cancelled.current) setNotice(t("voice.cancelled"));
      else setError(t("voice.errorHelp"));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    void run(refresh);
  }, []);
  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => {
      void invoke<string>("voice_phase")
        .then(setPhase)
        .catch(() => {});
    }, 800);
    return () => window.clearInterval(timer);
  }, [busy]);
  const changeProfile = (value: string) => {
    setProfile(value);
    setListened(false);
    setComparison(null);
    setCandidateAudio(null);
  };
  const folder = (target: string) => {
    void invoke("voice_open_folder", { target }).catch(() =>
      setError(t("voice.folderError")),
    );
  };
  const ready = storage?.runtimeReady && storage?.modelReady;
  const chosen = library.profiles.find((p) => p.id === profile);
  const startAdd = () => {
    setAdding(true);
    setDetail(null);
    setName("");
    setConfirmed(false);
    setSelected(null);
  };
  return (
    <section className="voice-studio" aria-label={t("voice.title")}>
      <header className="voice-heading">
        <div>
          <p className="voice-eyebrow">{t("voice.studioLabel")}</p>
          <h1>{t("voice.title")}</h1>
          <p className="voice-muted">{t("voice.subtitle")}</p>
        </div>
        <span className="voice-local">
          <ShieldCheck size={15} />
          {t("voice.onDevice")}
        </span>
      </header>
      <div className="voice-tabs" role="tablist" aria-label={t("voice.title")}>
        <button
          role="tab"
          id="voice-generate-tab"
          aria-controls="voice-generate-panel"
          aria-selected={tab === "generate"}
          onClick={() => setTab("generate")}
        >
          <Sparkles size={17} />
          {t("voice.generateTab")}
        </button>
        <button
          role="tab"
          id="voice-library-tab"
          aria-controls="voice-library-panel"
          aria-selected={tab === "library"}
          onClick={() => setTab("library")}
        >
          <AudioLines size={17} />
          {t("voice.libraryTab")}
          <span className="voice-count">{library.profiles.length}</span>
        </button>
      </div>
      {notice && (
        <p className="voice-message" role="status">
          {notice}
        </p>
      )}
      {error && (
        <div className="voice-error" role="alert">
          {error}
          <button disabled={busy} onClick={() => void run(refresh)}>
            {t("voice.refresh")}
          </button>
        </div>
      )}
      {tab === "generate" && (
        <div
          id="voice-generate-panel"
          role="tabpanel"
          aria-labelledby="voice-generate-tab"
          className="voice-stack"
        >
          {!busy && !ready && (
            <p className="voice-message">{t("voice.notReady")}</p>
          )}
          {library.profiles.length === 0 ? (
            <div className="voice-empty">
              <AudioLines size={32} />
              <h2>{t("voice.noProfiles")}</h2>
              <p>{t("voice.noProfilesHelp")}</p>
              <button
                className="voice-primary"
                onClick={() => {
                  setTab("library");
                  startAdd();
                }}
              >
                <Plus size={16} />
                {t("voice.addReference")}
              </button>
            </div>
          ) : (
            <>
              <div className="voice-panel voice-stack">
                <label htmlFor="voice-profile">{t("voice.profile")}</label>
                <div className="voice-profile-row">
                  <select
                    id="voice-profile"
                    value={profile}
                    disabled={busy}
                    onChange={(e) => changeProfile(e.target.value)}
                  >
                    {library.profiles.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                        {library.primary === p.id
                          ? ` · ${t("voice.primary")}`
                          : ` · ${t("voice.candidate")}`}
                      </option>
                    ))}
                  </select>
                  <button
                    className="voice-subtle"
                    onClick={() => setTab("library")}
                  >
                    {t("voice.manage")}
                  </button>
                </div>
                {chosen && (
                  <p className="voice-muted voice-small">
                    {t("voice.referenceDuration", {
                      seconds: chosen.seconds.toFixed(1),
                    })}
                  </p>
                )}
                <div className="voice-field-title">
                  <label htmlFor="voice-text">{t("voice.text")}</label>
                  <span className="voice-muted voice-small">
                    {t("voice.characters", { count: text.length })}
                  </span>
                </div>
                <textarea
                  id="voice-text"
                  maxLength={4000}
                  value={text}
                  disabled={busy}
                  placeholder={t("voice.textPlaceholder")}
                  onChange={(e) => setText(e.target.value)}
                />
                <p className="voice-muted voice-small">
                  {t("voice.dictionaryHelp")}
                </p>
                <div className="voice-actions">
                  <button
                    className="voice-primary"
                    disabled={busy || !profile || !text.trim() || !ready}
                    onClick={() =>
                      void run(async () => {
                        setResult(
                          await call<AudioResult>("generate", {
                            profile,
                            text,
                          }),
                        );
                      })
                    }
                  >
                    <Sparkles size={17} />
                    {t(
                      busy
                        ? `voice.${["loading", "generating"].includes(phase) ? phase : "working"}`
                        : "voice.generate",
                    )}
                  </button>
                  {busy && (
                    <button
                      className="voice-secondary"
                      onClick={() => {
                        cancelled.current = true;
                        void invoke("voice_cancel").catch(() =>
                          setError(t("voice.errorHelp")),
                        );
                      }}
                    >
                      {t("voice.cancel")}
                    </button>
                  )}
                </div>
                {busy && (
                  <p role="status" className="voice-muted voice-small">
                    {t("voice.waitHelp")}
                  </p>
                )}
              </div>
              {result && (
                <div className="voice-panel voice-stack">
                  <div className="voice-field-title">
                    <h2>{t("voice.result")}</h2>
                    <span className="voice-muted">
                      {t("voice.seconds", {
                        seconds: result.seconds.toFixed(1),
                      })}
                    </span>
                  </div>
                  <audio controls src={convertFileSrc(result.audio)} />
                  <div className="voice-actions">
                    <button
                      className="voice-primary"
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          const destination = await save({
                            defaultPath: "voice.wav",
                            filters: [{ name: "WAV", extensions: ["wav"] }],
                          });
                          if (destination) {
                            await invoke("voice_export", {
                              id: result.id,
                              destination,
                            });
                            setNotice(t("voice.saved"));
                          }
                        })
                      }
                    >
                      <Download size={16} />
                      {t("voice.save")}
                    </button>
                    <button
                      className="voice-secondary"
                      onClick={() => folder("outputs")}
                    >
                      <FolderOpen size={16} />
                      {t("voice.openResults")}
                    </button>
                  </div>
                  <p className="voice-path">{result.audio}</p>
                </div>
              )}
            </>
          )}
          {storage && (
            <div className="voice-storage">
              <FolderOpen size={18} />
              <div>
                <strong>{t("voice.autoSave")}</strong>
                <p className="voice-path">{storage.outputs}</p>
              </div>
              <button
                className="voice-subtle"
                onClick={() => folder("outputs")}
              >
                {t("voice.openFolder")}
              </button>
            </div>
          )}
        </div>
      )}
      {tab === "library" && (
        <div
          id="voice-library-panel"
          role="tabpanel"
          aria-labelledby="voice-library-tab"
          className="voice-stack"
        >
          <div className="voice-field-title">
            <div>
              <h2>{t("voice.libraryTab")}</h2>
              <p className="voice-muted voice-small">
                {t("voice.referenceHelp")}
              </p>
            </div>
            <button
              className="voice-primary"
              disabled={busy}
              onClick={startAdd}
            >
              <Plus size={16} />
              {t("voice.addReference")}
            </button>
          </div>
          {storage && (
            <div className="voice-storage">
              <FolderOpen size={20} />
              <div>
                <strong>{t("voice.referencesSaved")}</strong>
                <p className="voice-path">{storage.references}</p>
              </div>
              <button
                className="voice-subtle"
                onClick={() => folder("references")}
              >
                {t("voice.openFolder")}
              </button>
            </div>
          )}
          {library.profiles.length === 0 && !adding && (
            <p className="voice-message">{t("voice.noProfilesHelp")}</p>
          )}
          {library.profiles.map((p) => (
            <article
              key={p.id}
              className={`voice-panel voice-reference ${profile === p.id ? "voice-reference-selected" : ""}`}
            >
              <div className="voice-field-title">
                <div className="voice-min-width">
                  <h3>{p.name}</h3>
                  <p className="voice-muted voice-small">
                    {t("voice.seconds", { seconds: p.seconds.toFixed(1) })} ·{" "}
                    {t(
                      library.primary === p.id
                        ? "voice.primary"
                        : "voice.candidate",
                    )}
                  </p>
                </div>
                <button
                  className="voice-secondary"
                  disabled={busy || profile === p.id}
                  onClick={() => changeProfile(p.id)}
                >
                  {t(profile === p.id ? "voice.selected" : "voice.use")}
                </button>
              </div>
              <audio controls preload="none" src={convertFileSrc(p.audio)} />
            </article>
          ))}
          {adding && (
            <div className="voice-panel voice-stack">
              <div className="voice-field-title">
                <h2>{t("voice.addReference")}</h2>
                <button
                  className="voice-icon"
                  aria-label={t("voice.close")}
                  disabled={busy}
                  onClick={() => setAdding(false)}
                >
                  <X size={18} />
                </button>
              </div>
              <p className="voice-muted voice-small">
                {t("voice.importFormat")}
              </p>
              <div className="voice-actions">
                <button
                  className="voice-secondary"
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      const path = await open({
                        multiple: false,
                        filters: [{ name: "WAV", extensions: ["wav"] }],
                      });
                      if (typeof path === "string") {
                        setDetail({ audio: path, path, text: "" });
                        setSelected(null);
                        setConfirmed(false);
                      }
                    })
                  }
                >
                  {t("voice.chooseFile")}
                </button>
                <button
                  className="voice-secondary"
                  disabled={busy}
                  onClick={() =>
                    void run(async () =>
                      setHistory(await call<Recording[]>("history")),
                    )
                  }
                >
                  {t("voice.history")}
                </button>
              </div>
              {history.length > 0 && (
                <select
                  aria-label={t("voice.history")}
                  value={selected ?? ""}
                  disabled={busy}
                  onChange={(e) =>
                    void run(async () => {
                      const id = Number(e.target.value);
                      setSelected(id);
                      setConfirmed(false);
                      setDetail(await call("history_detail", { id }));
                    })
                  }
                >
                  <option value="" disabled>
                    {t("voice.chooseRecording")}
                  </option>
                  {history.map((h) => (
                    <option key={h.id} value={h.id}>
                      {new Date(h.timestamp * 1000).toLocaleString()}
                    </option>
                  ))}
                </select>
              )}
              {detail && (
                <>
                  <audio controls src={convertFileSrc(detail.audio)} />
                  <label htmlFor="voice-name">{t("voice.name")}</label>
                  <input
                    id="voice-name"
                    value={name}
                    maxLength={80}
                    placeholder={t("voice.namePlaceholder")}
                    disabled={busy}
                    onChange={(e) => setName(e.target.value)}
                  />
                  <label htmlFor="voice-transcript">
                    {t("voice.transcript")}
                  </label>
                  <textarea
                    id="voice-transcript"
                    className="voice-transcript"
                    value={detail.text}
                    maxLength={3000}
                    disabled={busy}
                    onChange={(e) => {
                      setConfirmed(false);
                      setDetail({ ...detail, text: e.target.value });
                    }}
                  />
                  <label className="voice-check">
                    <input
                      type="checkbox"
                      checked={confirmed}
                      disabled={busy}
                      onChange={(e) => setConfirmed(e.target.checked)}
                    />
                    <span>{t("voice.confirm")}</span>
                  </label>
                  <button
                    className="voice-primary"
                    disabled={
                      busy || !confirmed || !name.trim() || !detail.text.trim()
                    }
                    onClick={() =>
                      void run(async () => {
                        const entry = await call<Profile>(
                          detail.path ? "import_file" : "import",
                          {
                            id: selected,
                            path: detail.path,
                            name,
                            text: detail.text,
                            confirmed,
                          },
                        );
                        await refresh();
                        changeProfile(entry.id);
                        setDetail(null);
                        setAdding(false);
                        setNotice(t("voice.referenceAdded"));
                      })
                    }
                  >
                    {t("voice.add")}
                  </button>
                </>
              )}
            </div>
          )}
          {chosen && library.primary && profile !== library.primary && (
            <details className="voice-panel">
              <summary>{t("voice.compare")}</summary>
              <div className="voice-stack voice-comparison">
                <p className="voice-muted voice-small">
                  {t("voice.compareHelp")}
                </p>
                <button
                  className="voice-secondary"
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      setListened(false);
                      setComparison(null);
                      setCandidateAudio(null);
                      const sample = t("voice.sample");
                      setComparison(
                        await call("generate", {
                          profile: library.primary,
                          text: sample,
                        }),
                      );
                      setCandidateAudio(
                        await call("generate", { profile, text: sample }),
                      );
                    })
                  }
                >
                  {t("voice.compareButton")}
                </button>
                {comparison && (
                  <>
                    <p>{t("voice.primary")}</p>
                    <audio controls src={convertFileSrc(comparison.audio)} />
                  </>
                )}
                {candidateAudio && (
                  <>
                    <p>{t("voice.candidate")}</p>
                    <audio
                      controls
                      src={convertFileSrc(candidateAudio.audio)}
                    />
                  </>
                )}
                <label className="voice-check">
                  <input
                    type="checkbox"
                    checked={listened}
                    disabled={busy || !comparison || !candidateAudio}
                    onChange={(e) => setListened(e.target.checked)}
                  />
                  {t("voice.listened")}
                </label>
                <button
                  className="voice-secondary"
                  disabled={busy || !listened}
                  onClick={() =>
                    void run(async () => {
                      await call("approve", { profile, listened });
                      await refresh();
                      setListened(false);
                      setNotice(t("voice.primarySaved"));
                    })
                  }
                >
                  {t("voice.approve")}
                </button>
              </div>
            </details>
          )}
          {storage && (
            <details className="voice-panel">
              <summary>{t("voice.storageDetails")}</summary>
              <div className="voice-stack voice-comparison">
                <p className="voice-muted voice-small">
                  {t("voice.storageHelp")}
                </p>
                <strong>{t("voice.dictionary")}</strong>
                <p className="voice-path">{storage.dictionary}</p>
                <button
                  className="voice-secondary"
                  onClick={() => folder("root")}
                >
                  <FolderOpen size={16} />
                  {t("voice.openFolder")}
                </button>
              </div>
            </details>
          )}
        </div>
      )}
    </section>
  );
}

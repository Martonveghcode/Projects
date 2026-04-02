import { useCallback, useEffect, useMemo, useState } from "react";
import dayjs from "dayjs";
import { LogIn, LogOut, Plus, Settings } from "lucide-react";
import {
  loadGoogle,
  signIn,
  signOut,
  insertEvent,
  listCalendars,
} from "./lib/google";
import {
  getCfg,
  setCfg,
  getLessons,
  setLessons,
} from "./lib/storage";
import { uid } from "./lib/ui";
import { GOOGLE_COLOR_MAP } from "./lib/constants";
import { resolveLessonColorHex, resolveLessonColorId } from "./lib/events";
import LessonsPanel from "./components/LessonsPanel";
import CreateEventPanel from "./components/CreateEventPanel";
import SetupModal from "./components/SetupModal";
import LessonEditor from "./components/LessonEditor";

const TEST_CALENDAR_NAME = "TESTS";

const normalizeLesson = (lesson) => {
  if (!lesson) return lesson;
  const colorId = resolveLessonColorId(lesson);
  return {
    ...lesson,
    colorId,
    color: resolveLessonColorHex({ ...lesson, colorId }),
  };
};

const sanitizeLessonSlots = (slots = [], lessonIndex) => {
  if (!Array.isArray(slots)) {
    return [];
  }

  return slots
    .map((slot, slotIndex) => {
      if (!slot || typeof slot !== "object") {
        console.warn(`[import] Ignoring invalid slot at index ${slotIndex} for lesson ${lessonIndex}`);
        return null;
      }

      const weekday = Number(slot.weekday);
      const start = typeof slot.start === "string" ? slot.start : "";
      const end = typeof slot.end === "string" ? slot.end : "";

      if (!Number.isInteger(weekday) || weekday < 0 || weekday > 6) {
        console.warn(`[import] Ignoring slot with invalid weekday at index ${slotIndex} for lesson ${lessonIndex}`);
        return null;
      }

      if (!start || !end) {
        console.warn(`[import] Ignoring slot with missing time at index ${slotIndex} for lesson ${lessonIndex}`);
        return null;
      }

      return { weekday, start, end };
    })
    .filter(Boolean);
};

const prepareLessonsFromFile = (lessons) => {
  if (!Array.isArray(lessons)) {
    throw new Error("Lessons must be an array.");
  }

  return lessons.map((lesson, index) => {
    if (!lesson || typeof lesson !== "object") {
      throw new Error(`Lesson at index ${index} is not a valid object.`);
    }

    const name = typeof lesson.name === "string" ? lesson.name.trim() : "";
    if (!name) {
      throw new Error(`Lesson at index ${index} is missing a name.`);
    }

    const sanitized = {
      ...lesson,
      id: typeof lesson.id === "string" && lesson.id.trim() ? lesson.id.trim() : uid("lesson"),
      name,
      slots: sanitizeLessonSlots(lesson.slots, index),
    };

    return normalizeLesson(sanitized);
  });
};

export default function App() {
  const [cfg, setCfgState] = useState(() => getCfg());
  const [setupOpen, setSetupOpen] = useState(() => {
    const stored = getCfg();
    return !stored?.clientId || !stored?.apiKey;
  });
  const [lessons, setLessonsState] = useState(() => getLessons().map(normalizeLesson));
  const [editingLesson, setEditingLesson] = useState(null);

  const [googleReady, setGoogleReady] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleError, setGoogleError] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);

  const [testCalendarId, setTestCalendarId] = useState(null);
  const [testCalendarLookupAttempted, setTestCalendarLookupAttempted] = useState(false);

  const [eventFeedback, setEventFeedback] = useState(null);
  const [eventSubmitting, setEventSubmitting] = useState(false);

  const sortedLessons = useMemo(() => [...lessons].sort((a, b) => a.name.localeCompare(b.name)), [lessons]);
  const dataSnapshot = useMemo(
    () => ({
      cfg: cfg ? { ...cfg } : null,
      lessons: lessons.map((lesson) => ({ ...lesson })),
    }),
    [cfg, lessons]
  );

  useEffect(() => {
    setCfg(cfg);
  }, [cfg]);

  useEffect(() => {
    setLessons(lessons);
  }, [lessons]);

  useEffect(() => {
    let cancelled = false;

    if (cfg?.clientId && cfg?.apiKey) {
      setGoogleLoading(true);
      setGoogleError("");
      loadGoogle(cfg)
        .then(() => {
          if (!cancelled) {
            setGoogleReady(true);
          }
        })
        .catch((error) => {
          if (!cancelled) {
            setGoogleError(error.message || "Failed to load Google libraries");
            setGoogleReady(false);
          }
        })
        .finally(() => {
          if (!cancelled) {
            setGoogleLoading(false);
          }
        });
    } else {
      setGoogleReady(false);
    }

    return () => {
      cancelled = true;
    };
  }, [cfg]);

  useEffect(() => {
    if (!cfg?.clientId || !cfg?.apiKey) {
      try {
        signOut();
      } catch (_) {
        /* ignore */
      }
      setConnected(false);
    }
  }, [cfg]);

  const locateTestCalendar = useCallback(async () => {
    try {
      const calendars = await listCalendars();
      const match = calendars.find(
        (calendar) => (calendar.summary || "").trim().toLowerCase() === TEST_CALENDAR_NAME.toLowerCase()
      );
      const foundId = match?.id || null;
      setTestCalendarId(foundId);
      setTestCalendarLookupAttempted(true);
      return foundId;
    } catch (error) {
      setTestCalendarId(null);
      setTestCalendarLookupAttempted(true);
      throw error;
    }
  }, []);

  useEffect(() => {
    if (!connected) {
      setTestCalendarId(null);
      setTestCalendarLookupAttempted(false);
      return;
    }

    if (testCalendarLookupAttempted) {
      return;
    }

    locateTestCalendar().catch((error) => {
      console.warn(`[calendar] Failed to locate ${TEST_CALENDAR_NAME} calendar`, error);
    });
  }, [connected, locateTestCalendar, testCalendarLookupAttempted]);

  useEffect(() => {
    if (!eventFeedback) return undefined;
    const timer = window.setTimeout(() => setEventFeedback(null), 4000);
    return () => window.clearTimeout(timer);
  }, [eventFeedback]);

  const connectGoogle = useCallback(async () => {
    if (!googleReady) {
      setGoogleError("Add your Google API credentials first");
      setSetupOpen(true);
      return;
    }

    setConnecting(true);
    setGoogleError("");
    try {
      await signIn();
      setConnected(true);
    } catch (error) {
      setGoogleError(error.message || "Failed to connect to Google Calendar");
    } finally {
      setConnecting(false);
    }
  }, [googleReady]);

  const handleDisconnect = useCallback(() => {
    try {
      signOut();
    } catch (_) {
      /* ignore */
    }
    setConnected(false);
    setTestCalendarId(null);
    setTestCalendarLookupAttempted(false);
  }, []);

  const handleSaveCfg = useCallback(
    (nextCfg) => {
      setCfgState(nextCfg);
      setSetupOpen(false);
      handleDisconnect();
    },
    [handleDisconnect]
  );

  const handleCreateLesson = useCallback(() => {
    const now = dayjs();
    const start = now.add(1, "hour").startOf("hour");
    const end = start.add(1, "hour");
    const defaultColorId = "9";
    const defaultColor = GOOGLE_COLOR_MAP[defaultColorId]?.hex || "#5484ed";

    setEditingLesson({
      id: null,
      name: "",
      colorId: defaultColorId,
      color: defaultColor,
      slots: [
        {
          weekday: now.day(),
          start: start.format("HH:mm"),
          end: end.format("HH:mm"),
        },
      ],
    });
  }, []);

  const handleSaveLesson = useCallback((draft) => {
    const colorId = resolveLessonColorId(draft);
    const color = resolveLessonColorHex({ ...draft, colorId });
    const lesson = {
      ...draft,
      id: draft.id || uid("lesson"),
      name: draft.name.trim(),
      colorId,
      color,
      slots: draft.slots.map((slot) => ({
        weekday: Number(slot.weekday),
        start: slot.start,
        end: slot.end,
      })),
    };

    setLessonsState((prev) => {
      const existing = prev.find((item) => item.id === lesson.id);
      if (existing) {
        return prev.map((item) => (item.id === lesson.id ? lesson : item));
      }
      return [...prev, lesson];
    });

    setEditingLesson(null);
  }, []);

  const handleDeleteLesson = useCallback((lessonId) => {
    setLessonsState((prev) => prev.filter((item) => item.id !== lessonId));
    setEditingLesson(null);
  }, []);

  const handleImportData = useCallback(
    (payload) => {
      if (!payload || typeof payload !== "object") {
        throw new Error("The file must contain a JSON object.");
      }

      const applied = [];

      if (Object.prototype.hasOwnProperty.call(payload, "cfg")) {
        const incomingCfg = payload.cfg;
        if (incomingCfg === null) {
          setCfgState(null);
          applied.push("credentials");
          handleDisconnect();
        } else if (incomingCfg && typeof incomingCfg === "object") {
          const clientId = typeof incomingCfg.clientId === "string" ? incomingCfg.clientId.trim() : "";
          const apiKey = typeof incomingCfg.apiKey === "string" ? incomingCfg.apiKey.trim() : "";

          if (!clientId || !apiKey) {
            throw new Error("Credentials must include non-empty clientId and apiKey strings.");
          }

          setCfgState({ clientId, apiKey });
          applied.push("credentials");
          handleDisconnect();
        } else {
          throw new Error("Credentials section must be an object with clientId and apiKey.");
        }
      }

      if (Object.prototype.hasOwnProperty.call(payload, "lessons")) {
        const nextLessons = prepareLessonsFromFile(payload.lessons);
        setLessonsState(nextLessons);
        setEditingLesson(null);
        applied.push("lessons");
      }

      if (!applied.length) {
        throw new Error("The file does not include any recognized sections (cfg, lessons).");
      }

      return applied;
    },
    [handleDisconnect]
  );

  const handleCreateEvent = useCallback(
    async ({ summary, description, startISO, endISO, reminders, colorId, eventType }) => {
      setEventSubmitting(true);
      setEventFeedback(null);
      let success = false;

      try {
        let targetCalendarId = "primary";

        if (eventType === "test") {
          let calendarIdToUse = testCalendarId;
          if (!calendarIdToUse) {
            try {
              calendarIdToUse = await locateTestCalendar();
            } catch (calendarLookupError) {
              throw new Error(calendarLookupError.message || `Failed to locate ${TEST_CALENDAR_NAME} calendar`);
            }
          }

          if (!calendarIdToUse) {
            throw new Error(`Create a calendar named "${TEST_CALENDAR_NAME}" in Google Calendar to store tests.`);
          }

          targetCalendarId = calendarIdToUse;
        }

        const insertPayload = {
          summary,
          description,
          startISO,
          endISO,
          reminders,
          calendarId: targetCalendarId,
        };

        if (eventType !== "test" && colorId) {
          insertPayload.colorId = colorId;
        }

        await insertEvent(insertPayload);

        setEventFeedback({
          type: "success",
          message:
            eventType === "test"
              ? `Test event added to "${TEST_CALENDAR_NAME}".`
              : "Event added to Google Calendar.",
        });
        success = true;
      } catch (error) {
        setEventFeedback({ type: "error", message: error.message || "Failed to create event." });
      } finally {
        setEventSubmitting(false);
      }

      return success;
    },
    [locateTestCalendar, testCalendarId]
  );

  return (
    <div className="app-shell">
      <div className="app-container">
        <div className="app-surface">
          <header className="app-header">
            <div>
              <h1 className="app-title">Homework Calendar</h1>
              <p className="app-meta">
                {sortedLessons.length} lesson{sortedLessons.length === 1 ? "" : "s"}
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => setSetupOpen(true)}
                className="app-button"
              >
                <Settings className="h-4 w-4" />
                Setup
              </button>

              {connected ? (
                <button
                  type="button"
                  onClick={handleDisconnect}
                  className="app-button"
                >
                  <LogOut className="h-4 w-4" />
                  Disconnect Google
                </button>
              ) : (
                <button
                  type="button"
                  onClick={connectGoogle}
                  disabled={connecting || googleLoading}
                  className="app-button app-button-primary"
                >
                  <LogIn className="h-4 w-4" />
                  {connecting ? "Connecting..." : googleLoading ? "Loading Google..." : "Connect Google"}
                </button>
              )}

              <button
                type="button"
                onClick={handleCreateLesson}
                className="app-button"
              >
                <Plus className="h-4 w-4" />
                New lesson
              </button>
            </div>
          </header>

          {googleError && <div className="app-alert app-alert-error mt-6">{googleError}</div>}

          <main className="app-main">
            <CreateEventPanel
              lessons={sortedLessons}
              onCreate={handleCreateEvent}
              isConnected={connected}
              isSubmitting={eventSubmitting}
              feedback={eventFeedback}
            />

            <LessonsPanel
              lessons={sortedLessons}
              onEdit={setEditingLesson}
              onDelete={handleDeleteLesson}
            />
          </main>
        </div>
      </div>

      <SetupModal
        open={setupOpen}
        values={cfg}
        onSave={handleSaveCfg}
        onClose={!cfg ? undefined : () => setSetupOpen(false)}
        dataSnapshot={dataSnapshot}
        onImportData={handleImportData}
      />

      {editingLesson && (
        <LessonEditor
          lesson={editingLesson}
          onSave={handleSaveLesson}
          onCancel={() => setEditingLesson(null)}
          onDelete={editingLesson?.id ? handleDeleteLesson : undefined}
        />
      )}
    </div>
  );
}

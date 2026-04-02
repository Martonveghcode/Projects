import { useEffect, useMemo, useState } from "react";
import { Calendar } from "lucide-react";
import dayjs from "dayjs";
import { clsx, WEEKDAYS } from "../lib/ui";
import { EVENT_TYPES, REMINDER_TIMES, LOCAL_TIMEZONE } from "../lib/constants";
import {
  generateUpcomingDates,
  formatDateOption,
  buildSummary,
  buildDescription,
  resolveLessonColorHex,
  resolveLessonColorId,
} from "../lib/events";

export default function CreateEventPanel({ lessons, onCreate, isConnected, isSubmitting, feedback }) {
  const [lessonId, setLessonId] = useState(() => lessons[0]?.id || "");
  const [slotIndex, setSlotIndex] = useState("0");
  const [date, setDate] = useState("");
  const [eventType, setEventType] = useState(EVENT_TYPES[0].value);
  const [topic, setTopic] = useState("");
  const [notes, setNotes] = useState("");
  const [reminderDaysBefore, setReminderDaysBefore] = useState(2);
  const [reminderTime, setReminderTime] = useState(REMINDER_TIMES[0].value);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!lessons.length) {
      setLessonId("");
      setSlotIndex("");
      setDate("");
      return;
    }
    if (!lessons.some((lesson) => lesson.id === lessonId)) {
      const first = lessons[0];
      setLessonId(first.id);
      setSlotIndex(first.slots.length ? "0" : "");
      return;
    }
    const lesson = lessons.find((item) => item.id === lessonId);
    if (!lesson) return;
    if (!lesson.slots.length) {
      setSlotIndex("");
      setDate("");
      return;
    }
    if (!lesson.slots[Number(slotIndex)]) {
      setSlotIndex("0");
    }
  }, [lessons, lessonId, slotIndex]);

  const selectedLesson = lessons.find((lesson) => lesson.id === lessonId);
  const slots = selectedLesson?.slots || [];
  const chosenSlot = slots[Number(slotIndex)] || null;
  const lessonColorHex = selectedLesson ? resolveLessonColorHex(selectedLesson) : null;

  const availableDates = useMemo(() => generateUpcomingDates(chosenSlot), [chosenSlot]);

  useEffect(() => {
    if (!availableDates.length) {
      setDate("");
      return;
    }
    const options = availableDates.map((item) => item.format("YYYY-MM-DD"));
    if (!options.includes(date)) {
      setDate(options[0]);
    }
  }, [availableDates, date]);

  useEffect(() => {
    if (eventType === "test") {
      if (![1, 2].includes(reminderDaysBefore)) {
        setReminderDaysBefore(2);
      }
    } else if (eventType === "homework") {
      if (reminderDaysBefore !== 1) {
        setReminderDaysBefore(1);
      }
    }
  }, [eventType, reminderDaysBefore]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    if (!isConnected) {
      setError("Connect to Google Calendar first");
      return;
    }
    if (!selectedLesson) {
      setError("Add a lesson before creating events");
      return;
    }
    if (!slots.length) {
      setError("This lesson needs at least one weekly slot");
      return;
    }
    if (!chosenSlot) {
      setError("Select a time slot");
      return;
    }
    if (!date) {
      setError("Choose a date");
      return;
    }
    const slotWeekday = Number(chosenSlot.weekday);
    const selectedDate = dayjs(date);
    if (selectedDate.day() !== slotWeekday) {
      setError(`Selected date must be a ${WEEKDAYS[slotWeekday]}`);
      return;
    }
    if (chosenSlot.start >= chosenSlot.end) {
      setError("Slot end time must be after start time");
      return;
    }
    const [startHour, startMinute] = chosenSlot.start.split(":").map(Number);
    const [endHour, endMinute] = chosenSlot.end.split(":").map(Number);
    const start = selectedDate.hour(startHour).minute(startMinute).second(0).millisecond(0);
    const end = selectedDate.hour(endHour).minute(endMinute).second(0).millisecond(0);
    if (!end.isAfter(start)) {
      setError("End time must be after start time");
      return;
    }

    const summary = buildSummary(selectedLesson.name, eventType, topic);
    const description = buildDescription({
      lesson: selectedLesson,
      eventType,
      topic,
      notes,
      eventTypes: EVENT_TYPES,
    });
    const colorId = resolveLessonColorId(selectedLesson);

    let reminders = null;
    if (eventType === "test" || eventType === "homework") {
      const leadDays = eventType === "homework" ? 1 : reminderDaysBefore;
      const [remHour, remMinute] = reminderTime.split(":").map(Number);
      const reminderMoment = start
        .subtract(leadDays, "day")
        .hour(remHour)
        .minute(remMinute)
        .second(0)
        .millisecond(0);
      if (reminderMoment.isBefore(start)) {
        const minutesBefore = Math.max(0, Math.round(start.diff(reminderMoment, "minute")));
        reminders = [{ method: "popup", minutes: minutesBefore }];
      }
    }

    const success = await onCreate({
      summary,
      description,
      startISO: start.toISOString(),
      endISO: end.toISOString(),
      reminders,
      colorId,
      eventType,
    });

    if (success) {
      setTopic("");
      setNotes("");
    }
  };

  const reminderDayOptions = eventType === "test" ? [1, 2] : [1];

  return (
    <section className="rounded-2xl border p-6 shadow-soft" style={{ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)" }}>
      <h2 className="text-lg font-semibold">Create event</h2>
      <p className="mt-1 text-xs text-slate-300/80">
        Insert a Class, Test, or Homework into Google Calendar. Times use {LOCAL_TIMEZONE}.
      </p>
      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="event-lesson">
            Lesson
          </label>
          <div className="flex items-center gap-3">
            <select
              id="event-lesson"
              value={lessonId}
              onChange={(event) => setLessonId(event.target.value)}
              className="w-full rounded-xl border px-4 py-2 text-sm disabled:opacity-60"
              style={{ backgroundColor: "var(--theme-background)", borderColor: "var(--theme-border)", color: "var(--theme-text)" }}
              disabled={!lessons.length}
            >
              {!lessons.length && <option value="">No lessons yet</option>}
              {lessons.map((lesson) => (
                <option key={lesson.id} value={lesson.id}>
                  {lesson.name}
                </option>
              ))}
            </select>
            {lessonColorHex && (
              <span
                className="inline-flex h-6 w-6 flex-shrink-0 rounded-full border"
                style={{ backgroundColor: lessonColorHex, borderColor: "var(--theme-border)" }}
                aria-hidden="true"
              />
            )}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="event-slot">
              Weekly slot
            </label>
            <select
              id="event-slot"
              value={slotIndex}
              onChange={(event) => setSlotIndex(event.target.value)}
              className="w-full rounded-xl border px-4 py-2 text-sm"
              style={{ backgroundColor: "var(--theme-background)", borderColor: "var(--theme-border)", color: "var(--theme-text)" }}
              disabled={!slots.length}
            >
              {!slots.length && <option value="">No slots available</option>}
              {slots.map((slot, index) => (
                <option key={`${slot.weekday}-${slot.start}-${slot.end}`} value={index}>
                  {WEEKDAYS[slot.weekday]} | {slot.start} - {slot.end}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="event-date">
              Date
            </label>
            <select
              id="event-date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
              className="w-full rounded-xl border px-4 py-2 text-sm"
              style={{ backgroundColor: "var(--theme-background)", borderColor: "var(--theme-border)", color: "var(--theme-text)" }}
              disabled={!availableDates.length}
            >
              {!availableDates.length && <option value="">No upcoming dates</option>}
              {availableDates.map((dateOption) => {
                const value = dateOption.format("YYYY-MM-DD");
                return (
                  <option key={value} value={value}>
                    {formatDateOption(dateOption)}
                  </option>
                );
              })}
            </select>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-2">
            <label className="text-sm font-medium">Type</label>
            <div className="flex gap-2">
              {EVENT_TYPES.map((item) => (
                <button
                  type="button"
                  key={item.value}
                  onClick={() => setEventType(item.value)}
                  className={clsx(
                    "flex-1 rounded-xl px-3 py-2 text-sm font-medium transition",
                    eventType === item.value ? "btn-accent" : "border"
                  )}
                  style={
                    eventType === item.value
                      ? undefined
                      : { borderColor: "var(--theme-border)", backgroundColor: "var(--theme-background)" }
                  }
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="event-topic">
              Topic (optional)
            </label>
            <input
              id="event-topic"
              type="text"
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              className="w-full rounded-xl border px-4 py-2 text-sm"
              style={{ backgroundColor: "var(--theme-background)", borderColor: "var(--theme-border)", color: "var(--theme-text)" }}
              placeholder="DNA"
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="event-notes">
            Description (optional)
          </label>
          <textarea
            id="event-notes"
            rows={4}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className="w-full rounded-xl border px-4 py-2 text-sm"
            style={{ backgroundColor: "var(--theme-background)", borderColor: "var(--theme-border)", color: "var(--theme-text)" }}
            placeholder="Homework details, resources, room number..."
          />
        </div>

        {eventType !== "class" && (
          <div className="space-y-2">
            <label className="text-sm font-medium">Reminder</label>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <span className="text-xs uppercase tracking-wide text-slate-300/80">Days before</span>
                <select
                  value={reminderDaysBefore}
                  onChange={(event) => setReminderDaysBefore(Number(event.target.value))}
                  className="w-full rounded-xl border px-3 py-2 text-sm"
                  style={{ backgroundColor: "var(--theme-background)", borderColor: "var(--theme-border)", color: "var(--theme-text)" }}
                  disabled={eventType === "homework"}
                >
                  {reminderDayOptions.map((option) => (
                    <option key={option} value={option}>
                      {option} day{option === 1 ? "" : "s"} before
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <span className="text-xs uppercase tracking-wide text-slate-300/80">Reminder time</span>
                <select
                  value={reminderTime}
                  onChange={(event) => setReminderTime(event.target.value)}
                  className="w-full rounded-xl border px-3 py-2 text-sm"
                  style={{ backgroundColor: "var(--theme-background)", borderColor: "var(--theme-border)", color: "var(--theme-text)" }}
                >
                  {REMINDER_TIMES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-xl border px-4 py-3 text-sm" style={{ borderColor: "#f43f5e7f", color: "#fecdd3" }}>
            {error}
          </div>
        )}

        {feedback && (
          <div
            className="rounded-xl px-4 py-3 text-sm"
            style={feedback.type === "success" ? { border: "1px solid rgba(16, 185, 129, 0.4)", backgroundColor: "rgba(16, 185, 129, 0.15)", color: "#bbf7d0" } : { border: "1px solid #f43f5e7f", backgroundColor: "rgba(244, 63, 94, 0.15)", color: "#fecdd3" }}
          >
            {feedback.message}
          </div>
        )}

        <button
          type="submit"
          disabled={!isConnected || isSubmitting || !lessons.length || !availableDates.length}
          className="btn-accent flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold shadow-soft transition disabled:cursor-not-allowed disabled:opacity-80"
        >
          <Calendar className="h-4 w-4" />
          {isSubmitting ? "Creating..." : "Insert into Google Calendar"}
        </button>

        {!isConnected && (
          <p className="text-xs text-slate-300/80">
            Connect to Google Calendar to enable event creation.
          </p>
        )}
      </form>
    </section>
  );
}

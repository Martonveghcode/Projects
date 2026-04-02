import { useEffect, useMemo, useState } from "react";
import { Calendar } from "lucide-react";
import dayjs from "dayjs";
import { clsx, WEEKDAYS } from "../lib/ui";
import { EVENT_TYPES, REMINDER_TIMES } from "../lib/constants";
import {
  generateUpcomingDates,
  formatDateOption,
  buildSummary,
  buildDescription,
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
    } else if (eventType === "homework" && reminderDaysBefore !== 1) {
      setReminderDaysBefore(1);
    }
  }, [eventType, reminderDaysBefore]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");

    if (!isConnected) {
      setError("Connect Google first.");
      return;
    }

    if (!selectedLesson) {
      setError("Add a lesson first.");
      return;
    }

    if (!slots.length) {
      setError("This lesson needs at least one slot.");
      return;
    }

    if (!chosenSlot) {
      setError("Pick a slot.");
      return;
    }

    if (!date) {
      setError("Pick a date.");
      return;
    }

    const slotWeekday = Number(chosenSlot.weekday);
    const selectedDate = dayjs(date);

    if (selectedDate.day() !== slotWeekday) {
      setError(`Selected date must be ${WEEKDAYS[slotWeekday]}.`);
      return;
    }

    if (chosenSlot.start >= chosenSlot.end) {
      setError("Slot end time must be after start.");
      return;
    }

    const [startHour, startMinute] = chosenSlot.start.split(":").map(Number);
    const [endHour, endMinute] = chosenSlot.end.split(":").map(Number);
    const start = selectedDate.hour(startHour).minute(startMinute).second(0).millisecond(0);
    const end = selectedDate.hour(endHour).minute(endMinute).second(0).millisecond(0);

    if (!end.isAfter(start)) {
      setError("End time must be after start.");
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
  const submitLabel = isSubmitting
    ? "Creating..."
    : !isConnected
      ? "Connect Google first"
      : !lessons.length
        ? "Add a lesson first"
        : !availableDates.length
          ? "No matching dates"
          : "Add to Google Calendar";

  return (
    <section className="space-y-5">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="space-y-2">
          <label className="app-label" htmlFor="event-lesson">
            Lesson
          </label>
          <select
            id="event-lesson"
            value={lessonId}
            onChange={(event) => setLessonId(event.target.value)}
            className="app-field"
            disabled={!lessons.length}
          >
            {!lessons.length && <option value="">No lessons</option>}
            {lessons.map((lesson) => (
              <option key={lesson.id} value={lesson.id}>
                {lesson.name}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="app-label" htmlFor="event-slot">
              Slot
            </label>
            <select
              id="event-slot"
              value={slotIndex}
              onChange={(event) => setSlotIndex(event.target.value)}
              className="app-field"
              disabled={!slots.length}
            >
              {!slots.length && <option value="">No slots</option>}
              {slots.map((slot, index) => (
                <option key={`${slot.weekday}-${slot.start}-${slot.end}`} value={index}>
                  {WEEKDAYS[slot.weekday]} | {slot.start} - {slot.end}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label className="app-label" htmlFor="event-date">
              Date
            </label>
            <select
              id="event-date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
              className="app-field"
              disabled={!availableDates.length}
            >
              {!availableDates.length && <option value="">No dates</option>}
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
            <label className="app-label">Type</label>
            <div className="app-segmented">
              {EVENT_TYPES.map((item) => (
                <button
                  type="button"
                  key={item.value}
                  onClick={() => setEventType(item.value)}
                  className={clsx("app-segmented-button", eventType === item.value && "is-active")}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="app-label" htmlFor="event-topic">
              Topic
            </label>
            <input
              id="event-topic"
              type="text"
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              className="app-field"
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="app-label" htmlFor="event-notes">
            Notes
          </label>
          <textarea
            id="event-notes"
            rows={4}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className="app-field app-textarea"
          />
        </div>

        {eventType !== "class" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="app-label" htmlFor="event-reminder-days">
                Days before
              </label>
              <select
                id="event-reminder-days"
                value={reminderDaysBefore}
                onChange={(event) => setReminderDaysBefore(Number(event.target.value))}
                className="app-field"
                disabled={eventType === "homework"}
              >
                {reminderDayOptions.map((option) => (
                  <option key={option} value={option}>
                    {option} day{option === 1 ? "" : "s"} before
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="app-label" htmlFor="event-reminder-time">
                Reminder time
              </label>
              <select
                id="event-reminder-time"
                value={reminderTime}
                onChange={(event) => setReminderTime(event.target.value)}
                className="app-field"
              >
                {REMINDER_TIMES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {error && <div className="app-alert app-alert-error">{error}</div>}

        {feedback && (
          <div className={clsx("app-alert", feedback.type === "success" ? "app-alert-success" : "app-alert-error")}>
            {feedback.message}
          </div>
        )}

        <button
          type="submit"
          disabled={!isConnected || isSubmitting || !lessons.length || !availableDates.length}
          className="app-button app-button-primary w-full"
        >
          <Calendar className="h-4 w-4" />
          {submitLabel}
        </button>
      </form>
    </section>
  );
}

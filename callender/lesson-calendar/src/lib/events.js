import dayjs from "dayjs";
import { EVENT_TYPES, GOOGLE_COLORS, GOOGLE_COLOR_MAP } from "./constants";

export function generateUpcomingDates(slot, count = 12) {
  if (!slot) return [];
  const now = dayjs();
  const startOfToday = now.startOf("day");
  const weekday = Number(slot.weekday);
  if (Number.isNaN(weekday)) return [];
  const [hour, minute] = slot.start.split(":").map(Number);
  let firstCandidate = startOfToday.add((weekday - startOfToday.day() + 7) % 7, "day");
  let firstDate = firstCandidate
    .hour(hour)
    .minute(minute)
    .second(0)
    .millisecond(0);
  if (firstDate.isBefore(now)) {
    firstCandidate = firstCandidate.add(7, "day");
    firstDate = firstCandidate
      .hour(hour)
      .minute(minute)
      .second(0)
      .millisecond(0);
  }
  const dates = [];
  for (let index = 0; index < count; index += 1) {
    dates.push(firstDate.add(index * 7, "day"));
  }
  return dates;
}

export function formatDateOption(dateInstance) {
  return dateInstance.format("ddd, MMM D, YYYY");
}

export function buildSummary(lessonName, type, topic) {
  const trimmedTopic = topic.trim();
  if (type === "class") {
    return lessonName;
  }
  if (type === "test") {
    return `${lessonName} Test${trimmedTopic ? `: ${trimmedTopic}` : ""}`;
  }
  if (type === "homework") {
    return `${lessonName} Homework${trimmedTopic ? `: ${trimmedTopic}` : ""}`;
  }
  return lessonName;
}

export function buildDescription({ lesson, eventType, topic, notes }) {
  const displayType = EVENT_TYPES.find((item) => item.value === eventType)?.label || eventType;
  const lines = [`Lesson: ${lesson.name}`, `Type: ${displayType}`];
  if (topic.trim()) {
    lines.push(`Topic: ${topic.trim()}`);
  }
  if (notes.trim()) {
    lines.push("", notes.trim());
  }
  lines.push("", "Created with Lesson Calendar");
  return lines.join("\n");
}

export function cloneLesson(lesson) {
  if (!lesson) {
    return {
      id: null,
      name: "",
      colorId: "9",
      color: GOOGLE_COLOR_MAP["9"].hex,
      slots: [],
    };
  }
  const colorId = resolveLessonColorId(lesson);
  return {
    ...lesson,
    colorId,
    color: resolveLessonColorHex({ ...lesson, colorId }),
    slots: (lesson.slots || []).map((slot) => ({ ...slot })),
  };
}

export function resolveLessonColorId(lesson) {
  if (!lesson) return "9";
  if (lesson.colorId && GOOGLE_COLOR_MAP[lesson.colorId]) {
    return lesson.colorId;
  }
  if (lesson.color) {
    const hex = lesson.color.toLowerCase();
    const exact = GOOGLE_COLORS.find((color) => color.hex.toLowerCase() === hex);
    if (exact) return exact.id;
  }
  return "9";
}

export function resolveLessonColorHex(lesson) {
  const colorId = resolveLessonColorId(lesson);
  return GOOGLE_COLOR_MAP[colorId]?.hex || GOOGLE_COLOR_MAP["9"].hex;
}


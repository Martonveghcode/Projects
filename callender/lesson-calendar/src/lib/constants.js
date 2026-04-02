export const EVENT_TYPES = [
  { value: "class", label: "Class" },
  { value: "test", label: "Test" },
  { value: "homework", label: "Homework" },
];

export const REMINDER_TIMES = [
  { value: "16:00", label: "4:00 PM" },
  { value: "22:00", label: "10:00 PM" },
];

export const DEFAULT_THEME = {
  background: "#020617",
  surface: "#0f172a",
  border: "#334155",
  accent: "#0ea5e9",
  text: "#e2e8f0",
};

export const LOCAL_TIMEZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

export const GOOGLE_COLORS = [
  { id: "1", name: "Lavender", hex: "#a4bdfc" },
  { id: "2", name: "Sage", hex: "#7ae7bf" },
  { id: "3", name: "Grape", hex: "#dbadff" },
  { id: "4", name: "Flamingo", hex: "#ff887c" },
  { id: "5", name: "Banana", hex: "#fbd75b" },
  { id: "6", name: "Tangerine", hex: "#ffb878" },
  { id: "7", name: "Peacock", hex: "#46d6db" },
  { id: "8", name: "Graphite", hex: "#e1e1e1" },
  { id: "9", name: "Blueberry", hex: "#5484ed" },
  { id: "10", name: "Basil", hex: "#51b749" },
  { id: "11", name: "Tomato", hex: "#dc2127" },
];

export const GOOGLE_COLOR_MAP = GOOGLE_COLORS.reduce((map, color) => {
  map[color.id] = color;
  return map;
}, {});

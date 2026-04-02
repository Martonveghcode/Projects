import { useMemo } from "react";
import dayjs from "dayjs";
import { Calendar, ChevronLeft, ChevronRight } from "lucide-react";
import { WEEKDAYS } from "../lib/ui";

export default function CalendarGrid({ month, events, loading, error, connected, googleReady, onPrev, onNext }) {
  const days = useMemoDays(month);
  const eventsByDate = useMemoEvents(events);
  const today = dayjs();

  return (
    <section className="flex h-full flex-col overflow-hidden rounded-2xl border shadow-soft" style={{ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)" }}>
      <div className="flex items-center justify-between border-b px-6 py-4" style={{ borderColor: "var(--theme-border)" }}>
        <div className="flex items-center gap-2 text-lg font-semibold">
          <Calendar className="h-5 w-5" />
          {month.format("MMMM YYYY")}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onPrev}
            className="rounded-xl border p-2 transition"
            style={{ borderColor: "var(--theme-border)", backgroundColor: "var(--theme-background)", color: "var(--theme-text)" }}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onNext}
            className="rounded-xl border p-2 transition"
            style={{ borderColor: "var(--theme-border)", backgroundColor: "var(--theme-background)", color: "var(--theme-text)" }}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="grid grid-cols-7 gap-2 border-b px-6 py-3 text-xs uppercase tracking-wide text-slate-300/80" style={{ borderColor: "var(--theme-border)" }}>
        {WEEKDAYS.map((day) => (
          <span key={day} className="text-center">
            {day}
          </span>
        ))}
      </div>
      <div className="grid flex-1 grid-cols-7 gap-3 px-6 py-6">
        {days.map((day) => {
          const key = day.format("YYYY-MM-DD");
          const dayEvents = eventsByDate.get(key) || [];
          const overflow = Math.max(0, dayEvents.length - 3);
          const isCurrentMonth = day.month() === month.month();
          const isToday = day.isSame(today, "day");
          return (
            <div
              key={key}
              className="flex min-h-[130px] flex-col gap-2 rounded-2xl border px-3 py-3"
              style={{
                backgroundColor: isToday ? "rgba(14, 165, 233, 0.2)" : "var(--theme-background)",
                borderColor: isToday ? "rgba(14, 165, 233, 0.5)" : "var(--theme-border)",
                opacity: isCurrentMonth ? 1 : 0.6,
              }}
            >
              <div className="flex items-center justify-between text-xs" style={{ color: "var(--theme-text)" }}>
                <span className="text-sm font-semibold">{day.date()}</span>
                {isToday && (
                  <span className="text-[11px] font-medium uppercase" style={{ color: "var(--theme-accent)" }}>
                    Today
                  </span>
                )}
              </div>
              <div className="flex flex-1 flex-col gap-2">
                {dayEvents.slice(0, 3).map((event) => (
                  <div
                    key={event.id}
                    className="rounded-xl border px-3 py-2 text-xs"
                    title={event.summary}
                    style={{
                      backgroundColor: "var(--theme-surface)",
                      borderColor: event.colorHex || "var(--theme-border)",
                      color: "var(--theme-text)",
                    }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        {event.colorHex && (
                          <span
                            className="inline-flex h-2.5 w-2.5 rounded-full"
                            style={{ backgroundColor: event.colorHex }}
                            aria-hidden="true"
                          />
                        )}
                        <span className="font-medium line-clamp-1">{event.summary}</span>
                      </div>
                      <span className="text-[11px] text-slate-300/80">
                        {event.isAllDay ? "All day" : dayjs(event.startISO).format("HH:mm")}
                      </span>
                    </div>
                  </div>
                ))}
                {overflow > 0 && (
                  <div className="text-center text-[11px] text-slate-300/80">+{overflow} more</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <div className="border-t px-6 py-3 text-xs" style={{ borderColor: "var(--theme-border)", color: "var(--theme-text)" }}>
        {!googleReady && "Add Google credentials to load your calendar."}
        {googleReady && !connected && "Connect to Google Calendar to view events."}
        {loading && " Loading events..."}
        {error && <span style={{ color: "#fecdd3" }}> {error}</span>}
      </div>
    </section>
  );
}

function useMemoDays(month) {
  return useMemo(() => {
    const start = month.startOf("month").startOf("week");
    const end = month.endOf("month").endOf("week");
    const result = [];
    let cursor = start;
    while (cursor.isBefore(end) || cursor.isSame(end, "day")) {
      result.push(cursor);
      cursor = cursor.add(1, "day");
    }
    return result;
  }, [month]);
}

function useMemoEvents(events) {
  return useMemo(() => {
    const map = new Map();
    events.forEach((event) => {
      const key = dayjs(event.startISO).format("YYYY-MM-DD");
      const bucket = map.get(key) || [];
      bucket.push(event);
      map.set(key, bucket);
    });
    return map;
  }, [events]);
}


import { Clock, Edit3, Plus, Trash2 } from "lucide-react";
import { WEEKDAYS } from "../lib/ui";
import { resolveLessonColorHex } from "../lib/events";

export default function LessonsPanel({ lessons, onCreate, onEdit, onDelete }) {
  return (
    <section className="rounded-2xl border p-6 shadow-soft" style={{ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)" }}>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Your lessons</h2>
        <button
          type="button"
          onClick={onCreate}
          className="flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm font-medium transition"
          style={{ borderColor: "var(--theme-border)", backgroundColor: "var(--theme-background)", color: "var(--theme-text)" }}
        >
          <Plus className="h-4 w-4" />
          New
        </button>
      </div>
      {lessons.length === 0 ? (
        <p
          className="rounded-xl border border-dashed px-4 py-6 text-sm text-slate-300/80"
          style={{ backgroundColor: "var(--theme-background)", borderColor: "var(--theme-border)" }}
        >
          Add your first lesson to start planning recurring slots.
        </p>
      ) : (
        <ul className="space-y-4">
          {lessons.map((lesson) => {
            const colorHex = resolveLessonColorHex(lesson);
            return (
              <li key={lesson.id} className="rounded-2xl border p-4 transition" style={{ backgroundColor: "var(--theme-background)", borderColor: "var(--theme-border)" }}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="inline-flex h-3 w-3 rounded-full" style={{ backgroundColor: colorHex }} />
                      <h3 className="text-base font-semibold">{lesson.name}</h3>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {lesson.slots.map((slot, index) => (
                        <span
                          key={index}
                          className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs"
                          style={{ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)", color: "var(--theme-text)" }}
                        >
                          <Clock className="h-3 w-3 text-slate-300/80" />
                          {WEEKDAYS[slot.weekday]} | {slot.start} - {slot.end}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <button
                      type="button"
                      onClick={() => onEdit(lesson)}
                      className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1 text-xs font-medium transition"
                      style={{ borderColor: "var(--theme-border)", backgroundColor: "var(--theme-background)", color: "var(--theme-text)" }}
                    >
                      <Edit3 className="h-3.5 w-3.5" /> Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(lesson.id)}
                      className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1 text-xs font-medium transition"
                      style={{ borderColor: "#f43f5e7f", color: "#fecdd3" }}
                    >
                      <Trash2 className="h-3.5 w-3.5" /> Delete
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

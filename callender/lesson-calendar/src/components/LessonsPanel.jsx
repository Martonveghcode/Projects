import { Clock, Edit3, Trash2 } from "lucide-react";
import { WEEKDAYS } from "../lib/ui";
import { resolveLessonColorHex } from "../lib/events";

export default function LessonsPanel({ lessons, onEdit, onDelete }) {
  return (
    <section>
      <h2 className="app-section-title">Lessons</h2>

      {lessons.length === 0 ? (
        <p className="app-empty mt-6">No lessons yet.</p>
      ) : (
        <ul className="mt-6 space-y-4">
          {lessons.map((lesson) => {
            const colorHex = resolveLessonColorHex(lesson);
            return (
              <li key={lesson.id} className="lesson-card relative overflow-hidden">
                <div className="relative flex flex-col gap-4">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="space-y-2">
                      <div className="flex items-center gap-3">
                        <span className="inline-flex h-3 w-3 rounded-full" style={{ backgroundColor: colorHex }} />
                        <h3 className="text-xl font-semibold tracking-[-0.04em] text-white">{lesson.name}</h3>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => onEdit(lesson)}
                        className="app-button"
                      >
                        <Edit3 className="h-4 w-4" />
                        Edit
                      </button>

                      <button
                        type="button"
                        onClick={() => onDelete(lesson.id)}
                        className="app-button app-button-danger"
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </button>
                    </div>
                  </div>

                  <div className="grid gap-2">
                    {lesson.slots.map((slot, index) => (
                      <div key={index} className="lesson-slot">
                        <Clock className="h-4 w-4" />
                        <span className="font-medium text-white">
                          {WEEKDAYS[slot.weekday]} | {slot.start} - {slot.end}
                        </span>
                      </div>
                    ))}
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

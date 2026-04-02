import { useEffect, useMemo, useState } from "react";
import { Plus, Save, Trash2, X } from "lucide-react";
import { WEEKDAYS } from "../lib/ui";
import { GOOGLE_COLORS } from "../lib/constants";
import { cloneLesson, resolveLessonColorHex, resolveLessonColorId } from "../lib/events";

export default function LessonEditor({ lesson, onSave, onCancel, onDelete }) {
  const [draft, setDraft] = useState(() => cloneLesson(lesson));
  const [error, setError] = useState("");

  useEffect(() => {
    setDraft(cloneLesson(lesson));
    setError("");
  }, [lesson]);

  const isNew = !lesson?.id;
  const selectedColorId = draft.colorId || resolveLessonColorId(draft);
  const selectedColorHex = useMemo(() => resolveLessonColorHex(draft), [draft]);

  const updateSlot = (index, patch) => {
    setDraft((prev) => {
      const slots = prev.slots.map((slot, slotIndex) => {
        if (slotIndex !== index) return slot;
        return { ...slot, ...patch, weekday: Number(patch.weekday ?? slot.weekday) };
      });
      return { ...prev, slots };
    });
  };

  const removeSlot = (index) => {
    setDraft((prev) => ({
      ...prev,
      slots: prev.slots.filter((_, slotIndex) => slotIndex !== index),
    }));
  };

  const addSlot = () => {
    setDraft((prev) => ({
      ...prev,
      slots: [...prev.slots, { weekday: 1, start: "09:00", end: "10:00" }],
    }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();

    const name = draft.name.trim();
    if (!name) {
      setError("Lesson name is required.");
      return;
    }

    if (!draft.slots.length) {
      setError("Add at least one slot.");
      return;
    }

    const invalidSlot = draft.slots.find((slot) => !slot.start || !slot.end || slot.start >= slot.end);
    if (invalidSlot) {
      setError("Each slot needs a valid time range.");
      return;
    }

    const colorId = resolveLessonColorId(draft) || "9";
    const colorHex = resolveLessonColorHex({ ...draft, colorId });

    onSave({
      ...draft,
      name,
      colorId,
      color: colorHex,
      slots: draft.slots.map((slot) => ({
        weekday: Number(slot.weekday),
        start: slot.start,
        end: slot.end,
      })),
    });
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/75 px-4 py-6 backdrop-blur">
      <div className="app-modal overflow-y-auto">
        <div className="flex items-start justify-between gap-4">
          <h2 className="app-section-title">{isNew ? "New lesson" : "Edit lesson"}</h2>

          <button
            type="button"
            onClick={onCancel}
            className="app-button app-button-square"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-6">
          <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="space-y-2">
              <label className="app-label" htmlFor="lesson-name">
                Lesson name
              </label>
              <input
                id="lesson-name"
                type="text"
                value={draft.name}
                onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
                className="app-field"
              />
            </div>

            <div className="space-y-2">
              <label className="app-label">Google color</label>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {GOOGLE_COLORS.map((color) => {
                  const isSelected = color.id === selectedColorId;
                  return (
                    <button
                      key={color.id}
                      type="button"
                      onClick={() => setDraft((prev) => ({ ...prev, colorId: color.id }))}
                      className="rounded-[10px] px-3 py-2 text-left text-xs font-medium transition"
                      style={{
                        background: isSelected ? "#f5f5f8" : "var(--theme-surface-soft)",
                        color: isSelected ? "#0a0a0a" : "#f5f5f8",
                      }}
                    >
                      <span className="flex items-center gap-2">
                        <span className="inline-flex h-3.5 w-3.5 rounded-full" style={{ backgroundColor: color.hex }} />
                        {color.name}
                      </span>
                    </button>
                  );
                })}
              </div>

              <div className="app-inline-note flex items-center gap-2 pt-1">
                <span className="inline-flex h-3 w-3 rounded-full" style={{ backgroundColor: selectedColorHex }} />
                {GOOGLE_COLORS.find((color) => color.id === selectedColorId)?.name || "Blueberry"}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div className="app-inline-note">
                {draft.slots.length} slot{draft.slots.length === 1 ? "" : "s"}
              </div>

              <button
                type="button"
                onClick={addSlot}
                className="app-button"
              >
                <Plus className="h-4 w-4" />
                Add slot
              </button>
            </div>

            {draft.slots.length === 0 ? (
              <div className="app-empty">No slots yet.</div>
            ) : (
              <div className="space-y-3">
                {draft.slots.map((slot, index) => (
                  <div
                    key={index}
                    className="grid gap-3 rounded-[10px] bg-[color:var(--theme-surface-soft)] p-4 md:grid-cols-[1fr_1fr_1fr_auto]"
                  >
                    <div className="space-y-2">
                      <label className="app-label" htmlFor={`weekday-${index}`}>
                        Weekday
                      </label>
                      <select
                        id={`weekday-${index}`}
                        value={slot.weekday}
                        onChange={(event) => updateSlot(index, { weekday: Number(event.target.value) })}
                        className="app-field"
                      >
                        {WEEKDAYS.map((day, value) => (
                          <option key={day} value={value}>
                            {day}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-2">
                      <label className="app-label" htmlFor={`start-${index}`}>
                        Start
                      </label>
                      <input
                        id={`start-${index}`}
                        type="time"
                        value={slot.start}
                        onChange={(event) => updateSlot(index, { start: event.target.value })}
                        className="app-field"
                      />
                    </div>

                    <div className="space-y-2">
                      <label className="app-label" htmlFor={`end-${index}`}>
                        End
                      </label>
                      <input
                        id={`end-${index}`}
                        type="time"
                        value={slot.end}
                        onChange={(event) => updateSlot(index, { end: event.target.value })}
                        className="app-field"
                      />
                    </div>

                    <div className="flex items-end justify-end">
                      <button
                        type="button"
                        onClick={() => removeSlot(index)}
                        className="app-button app-button-danger"
                      >
                        <Trash2 className="h-4 w-4" />
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {error && <div className="app-alert app-alert-error">{error}</div>}

          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            {onDelete && lesson?.id ? (
              <button
                type="button"
                onClick={() => onDelete(lesson.id)}
                className="app-button app-button-danger"
              >
                <Trash2 className="h-4 w-4" />
                Delete lesson
              </button>
            ) : (
              <span className="app-inline-note" />
            )}

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onCancel}
                className="app-button"
              >
                Cancel
              </button>

              <button
                type="submit"
                className="app-button app-button-primary"
              >
                <Save className="h-4 w-4" />
                Save lesson
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

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
      slots: [
        ...prev.slots,
        { weekday: 1, start: "09:00", end: "10:00" },
      ],
    }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    const name = draft.name.trim();
    if (!name) {
      setError("Lesson name is required");
      return;
    }
    if (!draft.slots.length) {
      setError("Add at least one weekly slot");
      return;
    }
    const invalidSlot = draft.slots.find((slot) => !slot.start || !slot.end || slot.start >= slot.end);
    if (invalidSlot) {
      setError("Each slot needs a valid start/end time");
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
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 px-4 backdrop-blur">
      <div
        className="w-full max-w-2xl rounded-3xl border p-6 shadow-soft"
        style={{ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)" }}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{isNew ? "New lesson" : "Edit lesson"}</h2>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border px-2 py-2"
            style={{ borderColor: "var(--theme-border)", backgroundColor: "var(--theme-background)", color: "var(--theme-text)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="lesson-name">
                Lesson name
              </label>
              <input
                id="lesson-name"
                type="text"
                value={draft.name}
                onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
                className="w-full rounded-xl border px-4 py-2 text-sm"
                style={{
                  backgroundColor: "var(--theme-background)",
                  borderColor: "var(--theme-border)",
                  color: "var(--theme-text)",
                }}
                placeholder="Biology"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Google event color</label>
              <div className="rounded-2xl border p-3" style={{ borderColor: "var(--theme-border)", backgroundColor: "var(--theme-background)" }}>
                <div className="mb-3 flex items-center gap-2 text-xs text-slate-300/80">
                  <span className="inline-flex h-3 w-3 rounded-full" style={{ backgroundColor: selectedColorHex }} />
                  {GOOGLE_COLORS.find((color) => color.id === selectedColorId)?.name || "Blue"}
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {GOOGLE_COLORS.map((color) => {
                    const isSelected = color.id === selectedColorId;
                    return (
                      <button
                        key={color.id}
                        type="button"
                        onClick={() => setDraft((prev) => ({ ...prev, colorId: color.id }))}
                        className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium transition ${isSelected ? "shadow-soft" : "opacity-80"}`}
                        style={{
                          borderColor: isSelected ? "var(--theme-accent)" : "var(--theme-border)",
                          backgroundColor: "var(--theme-surface)",
                          color: "var(--theme-text)",
                        }}
                      >
                        <span className="inline-flex h-4 w-4 flex-shrink-0 rounded-full" style={{ backgroundColor: color.hex }} />
                        {color.name}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Weekly slots</span>
              <button
                type="button"
                onClick={addSlot}
                className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1 text-xs font-medium transition"
                style={{ borderColor: "var(--theme-border)", backgroundColor: "var(--theme-background)", color: "var(--theme-text)" }}
              >
                <Plus className="h-3.5 w-3.5" />
                Add slot
              </button>
            </div>
            {draft.slots.length === 0 ? (
              <p
                className="rounded-xl border border-dashed px-4 py-4 text-sm text-slate-300/80"
                style={{ backgroundColor: "var(--theme-background)", borderColor: "var(--theme-border)" }}
              >
                No slots yet. Add at least one weekday/time range.
              </p>
            ) : (
              <div className="space-y-3">
                {draft.slots.map((slot, index) => (
                  <div
                    key={index}
                    className="grid gap-3 rounded-2xl border p-4 md:grid-cols-[1fr_1fr_1fr_auto]"
                    style={{ backgroundColor: "var(--theme-background)", borderColor: "var(--theme-border)" }}
                  >
                    <div className="space-y-1">
                      <label className="text-xs uppercase tracking-wide text-slate-300/80">Weekday</label>
                      <select
                        value={slot.weekday}
                        onChange={(event) => updateSlot(index, { weekday: Number(event.target.value) })}
                        className="w-full rounded-xl border px-3 py-2 text-sm"
                        style={{ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)", color: "var(--theme-text)" }}
                      >
                        {WEEKDAYS.map((day, value) => (
                          <option key={day} value={value}>
                            {day}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs uppercase tracking-wide text-slate-300/80">Start</label>
                      <input
                        type="time"
                        value={slot.start}
                        onChange={(event) => updateSlot(index, { start: event.target.value })}
                        className="w-full rounded-xl border px-3 py-2 text-sm"
                        style={{ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)", color: "var(--theme-text)" }}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs uppercase tracking-wide text-slate-300/80">End</label>
                      <input
                        type="time"
                        value={slot.end}
                        onChange={(event) => updateSlot(index, { end: event.target.value })}
                        className="w-full rounded-xl border px-3 py-2 text-sm"
                        style={{ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)", color: "var(--theme-text)" }}
                      />
                    </div>
                    <div className="flex items-end justify-end">
                      <button
                        type="button"
                        onClick={() => removeSlot(index)}
                        className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition"
                        style={{ borderColor: "#f43f5e7f", color: "#fecdd3" }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {error && (
            <div className="rounded-xl border px-4 py-3 text-sm" style={{ borderColor: "#f43f5e7f", color: "#fecdd3" }}>
              {error}
            </div>
          )}

          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            {onDelete && lesson?.id ? (
              <button
                type="button"
                onClick={() => onDelete(lesson.id)}
                className="inline-flex items-center gap-1.5 rounded-xl border px-4 py-2 text-sm font-medium transition"
                style={{ borderColor: "#f43f5e7f", color: "#fecdd3" }}
              >
                <Trash2 className="h-4 w-4" /> Delete lesson
              </button>
            ) : (
              <span className="text-xs uppercase tracking-wide text-slate-300/80">
                {draft.slots.length} slot(s)
              </span>
            )}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onCancel}
                className="rounded-xl border px-4 py-2 text-sm font-medium transition"
                style={{ borderColor: "var(--theme-border)", backgroundColor: "var(--theme-background)", color: "var(--theme-text)" }}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn-accent inline-flex items-center gap-2 rounded-xl px-5 py-2 text-sm font-semibold shadow-soft transition"
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

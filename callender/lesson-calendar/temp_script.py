from pathlib import Path
path = Path('lesson-calendar/src/App.jsx')
text = path.read_text(encoding='utf-8')
start = text.index('function CreateEventPanel')
end = text.index('function CalendarGrid', start)
new_component = """
function CreateEventPanel({ lessons, onCreate, isConnected, isSubmitting, feedback }) {
  const [lessonId, setLessonId] = useState(() => lessons[0]?.id || "");
  const [slotIndex, setSlotIndex] = useState("0");
  const [date, setDate] = useState("");
  const [eventType, setEventType] = useState(EVENT_TYPES[0].value);
  const [topic, setTopic] = useState("");
  const [notes, setNotes] = useState("");
  const [reminderDaysBefore, setReminderDaysBefore] = useState(2);
  const [reminderTime, setReminderTime] = useState("16:00");
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
    const values = availableDates.map((item) => item.format("YYYY-MM-DD"));
    if (!values.includes(date)) {
      setDate(values[0]);
    }
  }, [availableDates, date]);

  useEffect(() => {
    if (eventType === "test") {
      if (reminderDaysBefore !== 1 and reminderDaysBefore !== 2):
        setReminderDaysBefore(2)
    } elif eventType == "homework":
      setReminderDaysBefore(1)
  }, [eventType, reminderDaysBefore])

import { initializeApp } from "firebase/app";
import { getDatabase, ref, onValue, push, set, remove } from "firebase/database";

const firebaseConfig = {
  databaseURL: "https://test-10701-default-rtdb.europe-west1.firebasedatabase.app/"
};
const app = initializeApp(firebaseConfig);
const db = getDatabase(app);
const dataBaseRef = ref(db, "tasks");

const deleteBtn = document.getElementById("clear-all");
const addTask = document.getElementById("add-task");
const taskDiv = document.getElementById("tasks");
let name = document.getElementById("taskname");

// 🧠 Function to render one task
function renderTask(taskName, key) {
  const div = document.createElement("div");
  const li = document.createElement("li");
  const checkbox = document.createElement("input");

  li.textContent = taskName;
  checkbox.type = "checkbox";

  checkbox.addEventListener("change", function () {
    if (checkbox.checked) {
      div.remove();
      // remove that one task from Firebase
      remove(ref(db, "tasks/" + key));
    }
  });

  div.appendChild(li);
  div.appendChild(checkbox);
  taskDiv.appendChild(div);
}

// ➕ Add new task
addTask.addEventListener("click", function () {
  const taskName = name.value.trim();
  if (!taskName) return;

  // Push new task to Firebase
  const newTaskRef = push(dataBaseRef);
  set(newTaskRef, { name: taskName });

  name.value = "";
});

// 🔁 Auto-render all tasks when data changes
onValue(dataBaseRef, (snapshot) => {
  taskDiv.innerHTML = ""; // clear list before re-rendering

  snapshot.forEach((childSnap) => {
    const task = childSnap.val();
    const key = childSnap.key;
    renderTask(task.name, key);
  });
});

// ❌ Clear all tasks
deleteBtn.addEventListener("click", function () {
  remove(dataBaseRef);  // removes all tasks from Firebase
  taskDiv.innerHTML = ""; // clears UI
});

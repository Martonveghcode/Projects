// index.js (loaded via Vite, <script type="module">)
import { initializeApp } from "firebase/app";
import { getDatabase, ref, set, get, child, push, onValue, remove } from "firebase/database";

// Use your real web config from Firebase console:
const firebaseConfig = {
  
  databaseURL: "https://test-10701-default-rtdb.europe-west1.firebasedatabase.app/"
}

const app = initializeApp(firebaseConfig)
const database = getDatabase(app)
const referenceInDB = ref(database, "websites")

console.log(database)


const inputEl = document.getElementById("input-el")
const inputBtn = document.getElementById("input-btn")
const ulEl = document.getElementById("ul-el")
const deleteBtn = document.getElementById("delete-btn")


onValue(referenceInDB, function(snapshot) {

  if (snapshot.exists()) {
    const snapshotValues = snapshot.val()
  const leads = Object.values(snapshotValues)
  render(leads)

  }


  
})



function render(leads) {
    let listItems = ""
    for (let i = 0; i < leads.length; i++) {
        listItems += `
            <li>
                <a target='_blank' href='${leads[i]}'>
                    ${leads[i]}
                </a>
            </li>
        `
    }
    ulEl.innerHTML = listItems
}

deleteBtn.addEventListener("dblclick", function() {
    remove(referenceInDB)
    ulEl.innerHTML = ""
   
    
})

inputBtn.addEventListener("click", function() {
    console.log(inputEl.value)
    
    push(referenceInDB, inputEl.value)
    
    inputEl.value = ""
    
    
})


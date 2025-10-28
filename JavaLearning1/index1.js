let saveButton = document.getElementById("input-btn")
const myLeads = []
const inputEl = document.getElementById("input-el")
const ulEl = document.getElementById("ul-el")


saveButton.addEventListener("click", function() {
    myLeads.push(inputEl.value)
    console.log(myLeads)
    inputEl.value=""
    renderLeads()
})
function renderLeads() {
    let listItems = ""
for (let i = 0; i < myLeads.length; i ++) {
    console.log(myLeads[i])
    listItems += `
    <li>
        <a href=${myLeads[i]} target="_blank">${myLeads[i]}</a>
    </li>`
}
    ulEl.innerHTML = listItems
}

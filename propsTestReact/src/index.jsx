import { createRoot } from "react-dom/client"
import App from "/src/App.jsx"
import data from "./data.js"   // you don't need /src/ when already inside src

const root = document.getElementById("root")
const main = createRoot(root)

main.render(
  <App num={data.numbers} />
)

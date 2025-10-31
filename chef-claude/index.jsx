import {createRoot} from "react-dom/client"
import Header from "./src/header"

const root = createRoot(document.getElementById("root"))

root.render(
    <>
        <Header/>
    </>
)
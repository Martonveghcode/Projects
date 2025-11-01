import {createRoot} from "react-dom/client"
import Header from "./src/header"
import Main from "./src/Main"

const root = createRoot(document.getElementById("root"))

root.render(
    <>
        <Header/>
        <Main/>
    </>
)
import {createRoot} from "react-dom/client"
import App from "./src/app"
import Subtract from "./src/subtracter"

const root = createRoot(document.getElementById("root"))

root.render(
    <>
        <App/>
        <Subtract/>

    </>
)
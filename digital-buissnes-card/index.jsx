import { createRoot } from "react-dom/client";
import App from "./components/app";
const rootc = document.getElementById("root")

const root = createRoot(rootc)

root.render(
    <App/>
)
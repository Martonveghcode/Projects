import Header from "./mainEl";
import { data } from "../../data";
export default function App() {
    const appElements = data.map((x) => {
        return <Header
            {...x }/>
    })

    return(
        <>{appElements}</>
        
    )
}
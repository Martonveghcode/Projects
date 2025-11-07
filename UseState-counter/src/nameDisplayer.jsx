import { useState } from "react"


export default function Name() {
    const Name = document.getElementById("nameInput")
    let [name, setName] = useState("a person")

    function handleName() {
        setName(name = Name.value   )
    }


    return(
        <>
            <input type="text" id="nameInput"/>
            <p>{name}</p>
            <button onClick={handleName}></button>
        </>
    )
}
import ReactMarkDown from "react-markdown"

export default function Recipe(props) {
    return(
        <>
            <section className="suggested-recipe-container" aria-live="polite">
                <ReactMarkDown>{props.thing.text}</ReactMarkDown>
            </section>
        </>)
    
}


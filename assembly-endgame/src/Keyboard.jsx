import clsx from "clsx"

export default function Keyboard(props) {
   const alphabet = "abcdefghijklmnopqrstuvwxyz"
   


    return (
        <>
        <section className="chips">{alphabet.split("").map((x) =>
             <button  onClick={() => props.letters(x)} key={x}
              className={clsx("keyboard", props.word.split("").includes(x) && props.letter.includes(x) ? "green" : "red")}>{x}</button>)}</section>
        
        </>
    )
}
export default function Keyboard() {
   const alphabet = "abcdefghijklmnopqrstuvwxyz"
   


    return (
        <>
        <section className="chips">{alphabet.split("").map((x) =>
             <button key={x} className="keyboard">{x}</button>)}</section>
        
        </>
    )
}
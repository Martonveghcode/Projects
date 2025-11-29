export default function Die(props) {
    const styles = {
        backgroundColor: props.isHeld ? "#59E391" : "white"
    }
    
    return (
        <button 
            style={styles}
            onClick={props.hold}
            aria-label="dice"
        >{props.value}</button>
    )
}
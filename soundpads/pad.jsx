



export default function Pad(props) {
    const styles = {
        backgroundColor: props.color
        
    }
    
    

    return(<button onClick={() =>  props.func(props.id)} className={props.on ? "on" : undefined} style={styles} ></button>)
}
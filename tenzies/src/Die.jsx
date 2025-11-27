

export default function Die(props) {
    
     
    

    return(
        <>
            <button className="die-Btn" style={props.isHeld ? {backgroundColor: "green"} :
             null } onClick={() => props.onBtn(props.id)}   >
                {props.value} 
            </button>
        </>
    )
}
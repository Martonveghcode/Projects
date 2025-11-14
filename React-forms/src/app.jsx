export default function App() {
  
  
  function Signup(formData) {
    const email = formData.get("email")
    console.log(email)

    const password = formData.get("password")
    console.log(password)

    const job = formData.getAll("job")
    console.log(job)

    const color = formData.get("fav-color")
    console.log(color)
    const data = Object.fromEntries(formData)
    
    const allData = {
      ...data,
      job
    }
    console.log(allData)
  }
  
  
  
  
    return (
    <section>
      <h1>Signup form</h1>
      <form action={Signup}>
        <label htmlFor="email">Email:</label>
        <input id="email" type="email" name="email" placeholder="joe@schmoe.com" />
        <br />
        
        <label htmlFor="password">Password:</label>
        <input id="password" type="password" name="password" placeholder="fmacnak" />

      <fieldset><input type="checkbox" value="firefighter" defaultChecked={true}  name="job"/>
        <label htmlFor="job">firefighter</label>
        <input type="checkbox" value="lawyer" name="job"/>
        <label htmlFor="job">lawyer</label>
        <input type="checkbox" value="cop" name="job"/>
        <label htmlFor="job">cop</label></fieldset>

      <label htmlFor="fav-color">what is your favoruite color</label>
      <select name="fav-color" id="fav-color" defaultValue="green">
        <option value="red">red</option>
        <option value="green">green</option>
      </select>
        
       

        
        <button type="submit">submit</button>
        
      </form>
    </section>
  )
}
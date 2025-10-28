let lowerCaseLetters = [
  'a','b','c','d','e','f','g','h','i','j','k','l','m',
  'n','o','p','q','r','s','t','u','v','w','x','y','z'
];

let upperCaseLetters = [
  'A','B','C','D','E','F','G','H','I','J','K','L','M',
  'N','O','P','Q','R','S','T','U','V','W','X','Y','Z'
];

let numbers = ['0','1','2','3','4','5','6','7','8','9'];

let symbols = [
  '!', '@', '#', '$', '%', '^', '&', '*', 
  '(', ')', '-', '_', '=', '+', '[', ']', 
  '{', '}', ';', ':', '"', "'", '<', '>', 
  ',', '.', '/', '?', '|', '\\', '`', '~'
];

let displayCount = document.getElementById("displayNum");
let charNum = 0;

function increment() {
    charNum++;
    displayCount.textContent = charNum + " character length";
}

function decrement() {
    if (charNum <= 1) {
        displayCount.textContent = charNum + " cannot make smaller";
    } else {
        charNum--;
        displayCount.textContent = charNum + " character length";
    }
}

let array1 = lowerCaseLetters.concat(symbols, upperCaseLetters, numbers);
let password = "";
let answerP = document.getElementById("answer")
function generatepassword() {
    password = ""; // reset each time
    for (let i = 0; i < charNum; i++) {
        password += array1[Math.floor(Math.random() * array1.length)];
    }
    answerP.textContent = password

    return password;
    
}

// Example: generate after user sets charNum
console.log(generatepassword());

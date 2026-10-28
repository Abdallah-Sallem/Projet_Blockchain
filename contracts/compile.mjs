import fs from 'node:fs';
import solc from 'solc';
const input={language:'Solidity',sources:{'FedTrace.sol':{content:fs.readFileSync(new URL('./FedTrace.sol',import.meta.url),'utf8')}},settings:{optimizer:{enabled:true,runs:200},viaIR:true,evmVersion:'shanghai',outputSelection:{'*':{'*':['abi','evm.bytecode.object']}}}};
const output=JSON.parse(solc.compile(JSON.stringify(input)));
if(output.errors?.some(e=>e.severity==='error'))throw Error(JSON.stringify(output.errors));
const contract=output.contracts['FedTrace.sol'].FedTrace;
fs.mkdirSync(new URL('./artifacts/',import.meta.url),{recursive:true});
fs.writeFileSync(new URL('./artifacts/FedTrace.json',import.meta.url),JSON.stringify({abi:contract.abi,bytecode:'0x'+contract.evm.bytecode.object},null,2));
console.log('FedTrace compiled with solc '+solc.version());

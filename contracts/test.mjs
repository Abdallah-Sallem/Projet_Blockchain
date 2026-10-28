import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ganache from 'ganache';
import {ethers} from 'ethers';
import './compile.mjs';
test('contract enforces gateway, signatures, roots, references, duplicates and history',async()=>{
 const engine=ganache.provider({logging:{quiet:true},chain:{hardfork:'shanghai'}});
 try{
 const provider=new ethers.BrowserProvider(engine);
 const gateway=await provider.getSigner(0),other=await provider.getSigner(1),author=ethers.Wallet.createRandom();
 const artifact=JSON.parse(fs.readFileSync(new URL('./artifacts/FedTrace.json',import.meta.url)));
 const contract=await new ethers.ContractFactory(artifact.abi,artifact.bytecode,gateway).deploy();await contract.waitForDeployment();
 const hash=s=>ethers.sha256(ethers.toUtf8Bytes(s));
 await (await contract.setWriter(author.address,2)).wait();
 await assert.rejects(()=>contract.connect(other).setWriter(author.address,1));
 const payload=ethers.toUtf8Bytes('{"schema":1}'),signature=await author.signMessage(ethers.getBytes(ethers.sha256(payload)));
 const root=[hash('root'),hash('history'),hash('experiment'),0,2,ethers.ZeroHash,hash('weights'),ethers.ZeroHash,[]];
 await assert.rejects(()=>contract.connect(other).anchor(root,payload,signature));
 await (await contract.anchor(root,payload,signature)).wait();
 assert.equal(await contract.verifyModel(root[0],root[6]),true);
 await (await contract.anchor(root,payload,signature)).wait();assert.equal(await contract.count(),1n);
 await assert.rejects(()=>contract.anchor(root,ethers.toUtf8Bytes('changed'),signature));
 await assert.rejects(()=>contract.anchor([hash('bad'),...root.slice(1,3),1,2,root[0],root[6],ethers.ZeroHash,[hash('missing')]],payload,signature));
 const badSig=await ethers.Wallet.createRandom().signMessage(ethers.getBytes(ethers.sha256(payload)));
 await assert.rejects(()=>contract.anchor([hash('newroot'),...root.slice(1)],payload,badSig));
 assert.equal((await contract.history(root[1])).length,1);
 assert.equal((await contract.getModelProvenance(root[0]))[0],ethers.ZeroHash);
 assert.equal(await contract.verifyDecision(hash('missing'),root[6],hash('explanation')),false);
 const clinic=ethers.Wallet.createRandom();await (await contract.setWriter(clinic.address,1)).wait();
 const clinicSignature=await clinic.signMessage(ethers.getBytes(ethers.sha256(payload)));
 const decision=[hash('decision'),hash('case'),root[2],0,3,root[0],root[6],hash('explanation'),[]];
 await (await contract.anchor(decision,payload,clinicSignature)).wait();
 assert.equal(await contract.verifyDecision(decision[0],root[6],hash('explanation')),true);
 assert.equal(await contract.verifyDecision(decision[0],root[6],hash('changed explanation')),false);
 }finally{await engine.disconnect()}
});

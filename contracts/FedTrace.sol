// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

/// @notice Educational EVM evidence registry. Authorized gateway validates JSON semantics.
contract FedTrace {
    struct Input {
        bytes32 id;
        bytes32 logicalKey;
        bytes32 experiment;
        uint64 round;
        uint8 kind; // 1 contribution, 2 model, 3 decision
        bytes32 parent;
        bytes32 modelHash;
        bytes32 explanationHash;
        bytes32[] references;
    }
    struct Record {
        Input fields;
        bytes payload;
        bytes signature;
        address author;
        uint64 timestamp;
    }
    address public immutable gateway;
    mapping(address => uint8) public roles; // 1 clinic, 2 server
    mapping(bytes32 => Record) private data;
    mapping(bytes32 => bytes32[]) private histories;
    bytes32[] public ids;
    event Anchored(bytes32 indexed id, bytes32 indexed logicalKey, uint8 kind, bytes32 payloadHash);

    constructor() { gateway = msg.sender; }
    modifier onlyGateway() { require(msg.sender == gateway,"unauthorized gateway"); _; }
    function setWriter(address writer, uint8 role) external onlyGateway {
        require(role <= 2,"role"); roles[writer] = role;
    }
    function anchor(Input calldata f, bytes calldata payload, bytes calldata signature) external onlyGateway {
        require(f.id != bytes32(0) && f.kind >= 1 && f.kind <= 3,"schema");
        bytes32 payloadHash = sha256(payload);
        if (data[f.id].timestamp != 0) {
            require(sha256(data[f.id].payload) == payloadHash && keccak256(abi.encode(data[f.id].fields)) == keccak256(abi.encode(f)),"conflicting duplicate");
            return;
        }
        require(signature.length == 65,"signature length");
        bytes32 r; bytes32 s; uint8 v;
        assembly { r := calldataload(signature.offset) s := calldataload(add(signature.offset,32)) v := byte(0,calldataload(add(signature.offset,64))) }
        require(uint256(s) <= 0x7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0 && (v == 27 || v == 28),"signature range");
        address author = ecrecover(keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32",payloadHash)),v,r,s);
        require(author != address(0) && roles[author] == (f.kind == 2 ? 2 : 1),"unauthorized author");
        if (f.kind == 2 && f.round == 0) {
            require(f.parent == 0 && f.references.length == 0,"root");
        } else {
            Record storage parent = data[f.parent];
            require(parent.timestamp != 0 && parent.fields.kind == 2 && parent.fields.experiment == f.experiment,"parent");
            require(f.kind == 3 ? parent.fields.round == f.round : parent.fields.round + 1 == f.round,"round");
            if (f.kind == 3) require(parent.fields.modelHash == f.modelHash,"model hash");
            if (f.kind == 2) {
                require(f.references.length > 0,"contributions");
                for (uint i=0;i<f.references.length;i++) {
                    Record storage c = data[f.references[i]];
                    require(c.timestamp != 0 && c.fields.kind == 1 && c.fields.round == f.round && c.fields.experiment == f.experiment && c.fields.parent == f.parent,"reference");
                    for(uint j=0;j<i;j++) require(f.references[j] != f.references[i] && data[f.references[j]].author != c.author,"duplicate clinic");
                }
            }
        }
        data[f.id] = Record(f,payload,signature,author,uint64(block.timestamp));
        ids.push(f.id); histories[f.logicalKey].push(f.id);
        emit Anchored(f.id,f.logicalKey,f.kind,payloadHash);
    }
    function get(bytes32 id) external view returns(Record memory) { return data[id]; }
    function count() external view returns(uint) { return ids.length; }
    function history(bytes32 logicalKey) external view returns(bytes32[] memory) { return histories[logicalKey]; }
    function verifyModel(bytes32 id,bytes32 hash) external view returns(bool) {
        return data[id].timestamp != 0 && data[id].fields.kind == 2 && data[id].fields.modelHash == hash;
    }
    function verifyDecision(bytes32 id,bytes32 modelHash,bytes32 explanationHash) external view returns(bool) {
        Record storage d = data[id];
        return d.timestamp != 0 && d.fields.kind == 3 && d.fields.modelHash == modelHash
            && d.fields.explanationHash == explanationHash && data[d.fields.parent].fields.modelHash == modelHash;
    }
    function getModelProvenance(bytes32 id) external view returns(bytes32 parent,bytes32[] memory contributions) {
        require(data[id].timestamp != 0 && data[id].fields.kind == 2,"model");
        return (data[id].fields.parent,data[id].fields.references);
    }
}

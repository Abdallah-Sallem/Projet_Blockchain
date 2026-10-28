import {test} from 'node:test';
import assert from 'node:assert/strict';
import {stateLabel} from '../src/states.mjs';
test('pending, tampered and uncertified remain distinct',()=>{
  assert.equal(stateLabel('pending'),'En attente');
  assert.equal(stateLabel('tampered'),'Falsifié');
  assert.equal(stateLabel('uncertified'),'Non certifié');
  assert.notEqual(stateLabel('submitted'),stateLabel('confirmed'));
});

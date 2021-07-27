from brownie import *
"""
Given the Vault for wBTC
Does it automatically set up with the tokens we expect?
"""

def test_setup_address(
    chain,
    accounts,
    token,
    vault,
    strategy,
    user,
    strategist,
    amount,
    RELATIVE_APPROX,
    lpComponent,
    borrowed,
    reward,
    incentivesController,
):
  assert strategy.aToken() == lpComponent
  assert strategy.vToken() == borrowed
  assert strategy.DECIMALS() == token.decimals()

  address_provider = Contract.from_explorer(strategy.ADDRESS_PROVIDER())
  
  assert strategy.LENDING_POOL() == address_provider.getLendingPool()
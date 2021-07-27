import brownie
from brownie import *
import pytest

"""
All manual tests permissions
All leverage tweaks permissions
"""

def test_permissions_manualDivestFromAAVE(levered_strat, gov, user, management):
  chain.sleep(1) ## Seems like otherwise it loose tracks of funds when re-setting
  with brownie.reverts():
    levered_strat.manualDivestFromAAVE({"from": user})
  
  levered_strat.manualDivestFromAAVE({"from": gov})
  levered_strat.manualDivestFromAAVE({"from": management})


def test_permissions_manualLeverUp(levered_strat, gov, user, management):
  chain.sleep(1) ## Seems like otherwise it loose tracks of funds when re-setting
  with brownie.reverts():
    levered_strat.manualLeverUp({"from": user})
  
  levered_strat.manualLeverUp({"from": gov})
  levered_strat.manualLeverUp({"from": management})


def test_permissions_manualWithdrawStepFromAAVE(levered_strat, gov, user, management):
  chain.sleep(1) ## Seems like otherwise it loose tracks of funds when re-setting
  with brownie.reverts():
    levered_strat.manualWithdrawStepFromAAVE(10, {"from": user})
  
  levered_strat.manualWithdrawStepFromAAVE(10, {"from": gov})
  levered_strat.manualWithdrawStepFromAAVE(10, {"from": management})


def test_permissions_manualRepayFromManager(levered_strat, gov, user, management, token):
  chain.sleep(1) ## Seems like otherwise it loose tracks of funds when re-setting

  token.approve(levered_strat, 10, {"from": user}) ## Gov has a little bit of performance fees
  token.approve(levered_strat, 10, {"from": gov}) ## Gov has a little bit of performance fees
  token.approve(levered_strat, 10, {"from": management}) ## Gov has a little bit of performance fees

  with brownie.reverts():
    levered_strat.manualRepayFromManager(10, {"from": user})
  
  levered_strat.manualRepayFromManager(10, {"from": gov})
  levered_strat.manualRepayFromManager(10, {"from": management})

def test_permissions_manualClaimRewards(levered_strat, gov, user, management):
  chain.sleep(1) ## Seems like otherwise it loose tracks of funds when re-setting

  with brownie.reverts():
    levered_strat.manualClaimRewards({"from": user})
  
  levered_strat.manualClaimRewards({"from": gov})
  levered_strat.manualClaimRewards({"from": management})

def test_permissions_manualCooldownRewards_gov(levered_strat, gov, user, management):
  chain.sleep(1) ## Seems like otherwise it loose tracks of funds when re-setting
  levered_strat.manualClaimRewards({"from": gov})

  with brownie.reverts():
    levered_strat.manualCooldownRewards({"from": user})
  
  levered_strat.manualCooldownRewards({"from": gov})

def test_permissions_manualCooldownRewards_management(levered_strat, gov, user, management):
  chain.sleep(1) ## Seems like otherwise it loose tracks of funds when re-setting
  levered_strat.manualClaimRewards({"from": management})
  with brownie.reverts():
    levered_strat.manualCooldownRewards({"from": user})
  
  levered_strat.manualCooldownRewards({"from": management})

def test_permissions_manualRedeemRewards_gov(levered_strat, gov, user, management):
  chain.sleep(1) ## Seems like otherwise it loose tracks of funds when re-setting
  levered_strat.manualClaimRewards({"from": gov})

  levered_strat.manualCooldownRewards({"from": gov})
  chain.sleep(3600 * 24 * 11)  # 10 days to unlock, extra time for caution

  with brownie.reverts():
    levered_strat.manualRedeemRewards({"from": user})
  
  levered_strat.manualRedeemRewards({"from": gov})

def test_permissions_manualRedeemRewards_management(levered_strat, gov, user, management):
  chain.sleep(1) ## Seems like otherwise it loose tracks of funds when re-setting
  levered_strat.manualClaimRewards({"from": management})

  levered_strat.manualCooldownRewards({"from": management})
  chain.sleep(3600 * 24 * 11)  # 10 days to unlock, extra time for caution

  with brownie.reverts():
    levered_strat.manualRedeemRewards({"from": user})
  
  levered_strat.manualRedeemRewards({"from": management})

def test_permissions_manualSwapFromStkAAVEToAAVE_user_gov(levered_strat, gov, user, management, reward):
  chain.sleep(1) ## Seems like otherwise it loose tracks of funds when re-setting

  levered_strat.manualClaimRewards({"from": gov})

  with brownie.reverts():
    levered_strat.manualSwapFromStkAAVEToAAVE(reward.balanceOf(levered_strat), 10 ** 18 * .95, {"from": user})
  
  levered_strat.manualSwapFromStkAAVEToAAVE(reward.balanceOf(levered_strat), 10 ** 18 * .95, {"from": gov})

def test_permissions_manualSwapFromStkAAVEToAAVE_user_management(levered_strat, gov, user, management, reward):
  chain.sleep(1) ## Seems like otherwise it loose tracks of funds when re-setting

  levered_strat.manualClaimRewards({"from": management})

  levered_strat.manualSwapFromStkAAVEToAAVE(reward.balanceOf(levered_strat), 10 ** 18 * .95, {"from": management})


def test_permissions_manualSwapFromAAVEToWant_gov(levered_strat, gov, user, management, reward, aave):
  levered_strat.manualClaimRewards({"from": gov})

  levered_strat.manualSwapFromStkAAVEToAAVE(reward.balanceOf(levered_strat), 10 ** 18 * .95, {"from": gov})

  with brownie.reverts():
    levered_strat.manualSwapFromAAVEToWant(aave.balanceOf(levered_strat), 0.00589100 * 10 ** 8, {"from": user})
  
  levered_strat.manualSwapFromAAVEToWant(aave.balanceOf(levered_strat), 0.00589100 * 10 ** 8, {"from": gov})

def test_permissions_manualSwapFromAAVEToWant_management(levered_strat, gov, user, management, reward, aave):
  levered_strat.manualClaimRewards({"from": gov})

  levered_strat.manualSwapFromStkAAVEToAAVE(reward.balanceOf(levered_strat), 10 ** 18 * .95, {"from": management})

  with brownie.reverts():
    levered_strat.manualSwapFromAAVEToWant(aave.balanceOf(levered_strat), 0.00589100 * 10 ** 8, {"from": user})
  
  levered_strat.manualSwapFromAAVEToWant(aave.balanceOf(levered_strat), 0.00589100 * 10 ** 8, {"from": management})
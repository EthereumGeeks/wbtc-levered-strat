// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

// These are the core Yearn libraries
import {
    BaseStrategy,
    StrategyParams,
    VaultAPI
} from "@yearnvaults/contracts/BaseStrategy.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

import {IStakedAave} from "../interfaces/aave/IStakedAave.sol";
import {ILendingPool} from "../interfaces/aave/ILendingPool.sol";
import {
    IAaveIncentivesController
} from "../interfaces/aave/IAaveIncentivesController.sol";
import {
    ILendingPoolAddressesProvider
} from "../interfaces/aave/ILendingPoolAddressesProvider.sol";
import {IPriceOracle} from "../interfaces/aave/IPriceOracle.sol";
import {DataTypes} from "../interfaces/aave/types/DataTypes.sol";

import {ISwapRouter} from "../interfaces/uniswap/ISwapRouter.sol";

contract Strategy is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    ILendingPoolAddressesProvider public constant ADDRESS_PROVIDER =
        ILendingPoolAddressesProvider(
            0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5
        );

    IERC20 public immutable aToken;
    IERC20 public immutable vToken;
    ILendingPool public immutable LENDING_POOL;

    uint256 public immutable DECIMALS; // For toETH conversion

    // stkAAVE
    IERC20 public constant reward =
        IERC20(0x4da27a545c0c5B758a6BA100e3a049001de870f5); // Token we farm and swap to want / aToken

    // Hardhcoded from the Liquidity Mining docs: https://docs.aave.com/developers/guides/liquidity-mining
    IAaveIncentivesController public constant INCENTIVES_CONTROLLER =
        IAaveIncentivesController(0xd784927Ff2f95ba542BfC824c8a8a98F3495f6b5);

    // For Swapping
    ISwapRouter public constant ROUTER =
        ISwapRouter(0xE592427A0AEce92De3Edee1F18E0157C05861564);

    IERC20 public constant AAVE_TOKEN =
        IERC20(0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9);
    IERC20 public constant WETH_TOKEN =
        IERC20(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);

    uint256 public constant VARIABLE_RATE = 2;
    uint16 public constant REFERRAL_CODE = 0;

    // Min Price we tollerate when swapping from stkAAVE to AAVE
    uint256 public minStkAAVEPRice = 9500; // 95%

    uint256 public minAAVEToWantPrice = 8000; // 80% // Seems like Oracle is slightly off

    // Should we harvest before prepareMigration
    bool public harvestBeforeMigrate = true;

    // Should we ensure the swap will be within slippage params before performing it during normal harvest?
    bool public checkSlippageOnHarvest = true;

    // Leverage
    uint256 public constant MAX_BPS = 10000;
    uint256 public minHealth = 1080000000000000000; // 1.08 with 18 decimals this is slighly above 70% tvl
    uint256 public minRebalanceAmount = 50000000; // 0.5 should be changed based on decimals (btc has 8)

    // How many times should we loop around?
    uint256 public maxIterations = 5;

    constructor(address _vault) public BaseStrategy(_vault) {
        // You can set these parameters on deployment to whatever you want
        maxReportDelay = 6300;
        profitFactor = 100;
        debtThreshold = 0;

        // Get lending Pool
        ILendingPool lendingPool =
            ILendingPool(ADDRESS_PROVIDER.getLendingPool());

        // Set lending pool as immutable
        LENDING_POOL = lendingPool;

        // Get Tokens Addresses
        DataTypes.ReserveData memory data =
            lendingPool.getReserveData(address(want));

        // Get aToken
        aToken = IERC20(data.aTokenAddress);

        // Get vToken
        vToken = IERC20(data.variableDebtTokenAddress);

        // Get Decimals
        DECIMALS = ERC20(address(want)).decimals();

        want.safeApprove(address(lendingPool), type(uint256).max);
        reward.safeApprove(address(ROUTER), type(uint256).max);
        AAVE_TOKEN.safeApprove(address(ROUTER), type(uint256).max);
    }

    // Set min health, stkToAAVE conv, AAVE to Want Conv and minRebalanceAmount
    function setMinHealth(uint256 newMinHealth) external onlyVaultManagers {
        require(newMinHealth >= 1000000000000000000); // dev: minHealth
        minHealth = newMinHealth;
    }

    function setMinStkAAVEPrice(uint256 newMinStkAAVEPRice)
        external
        onlyVaultManagers
    {
        require(newMinStkAAVEPRice >= 0 && newMinStkAAVEPRice <= MAX_BPS); // dev: minStkAAVEPRice
        minStkAAVEPRice = newMinStkAAVEPRice;
    }

    function setMinAAVEWantToPrice(uint256 newMinAAVEToWantPrice)
        external
        onlyVaultManagers
    {
        require(newMinAAVEToWantPrice >= 0 && newMinAAVEToWantPrice <= MAX_BPS); // dev: minAAVEToWantPrice
        minAAVEToWantPrice = newMinAAVEToWantPrice;
    }

    function setMinRebalanceAmount(uint256 newMinRebalanceAmount)
        external
        onlyVaultManagers
    {
        require(newMinRebalanceAmount > 0); // dev: minRebalanceAmount
        minRebalanceAmount = newMinRebalanceAmount;
    }

    // Should we harvest before migrate, should we check slippage on harvest?
    function setShouldHarvestBeforeMigrate(bool newHarvestBeforeMigrate)
        external
        onlyVaultManagers
    {
        harvestBeforeMigrate = newHarvestBeforeMigrate;
    }

    function setShouldCheckSlippageOnHarvest(bool newCheckSlippageOnHarvest)
        external
        onlyVaultManagers
    {
        checkSlippageOnHarvest = newCheckSlippageOnHarvest;
    }

    // ******** OVERRIDE THESE METHODS FROM BASE CONTRACT ************

    function name() external view override returns (string memory) {
        // Add your own name here, suggestion e.g. "StrategyCreamYFI"
        return "Strategy-Levered-AAVE-wBTC";
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        // Balance of want + balance in AAVE
        uint256 liquidBalance =
            want.balanceOf(address(this)).add(deposited()).sub(borrowed());

        // Return balance + reward
        return liquidBalance.add(valueOfRewards());
    }

    function prepareReturn(uint256 _debtOutstanding)
        internal
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        )
    {
        // NOTE: This means that if we are paying back we just deleverage
        // While if we are not paying back, we are harvesting rewards

        // Get current amount of want // used to estimate profit
        uint256 beforeBalance = want.balanceOf(address(this));

        // Claim stkAAVE -> swap into want
        _claimRewardsAndGetMoreWant();

        (uint256 earned, uint256 lost) = _repayAAVEBorrow(beforeBalance);

        if (_debtOutstanding > 0) {
            // Get it all out
            _divestFromAAVE();

            // Repay debt
            uint256 maxRepay = want.balanceOf(address(this));
            if (_debtOutstanding > maxRepay) {
                // we can't pay all, means we lost some
                _loss = _debtOutstanding.sub(maxRepay);
                _debtPayment = maxRepay;
            } else {
                // We can pay all, let's do it
                _debtPayment = _debtOutstanding;
                // Profit has to be the amount above Vault.debt
                // What's left is our profit
                uint256 initialDebt =
                    VaultAPI(vault).strategies(address(this)).totalDebt;

                // In repaying we may report a profit or a loss
                // In this case we have profit
                if (maxRepay.sub(_debtOutstanding) > initialDebt) {
                    // We have some profit
                    _profit = maxRepay.sub(initialDebt).sub(_debtOutstanding);
                }
                // In this case we have Loss
                if (maxRepay < initialDebt) {
                    // We have some loss
                    _loss = initialDebt.sub(maxRepay);
                }
            }
        } else {
            // In case of normal harvest, just return the value from `_repayAAVEBorrow`
            _debtPayment = 0;
            _profit = earned;
            _loss = lost;
        }
    }

    function _repayAAVEBorrow(uint256 beforeBalance)
        internal
        returns (uint256 _profit, uint256 _loss)
    {
        // Calculate Gain from AAVE interest // NOTE: This should never happen as we take more debt than we earn
        uint256 currentWantInAave = deposited().sub(borrowed());
        uint256 initialDeposit = vault.strategies(address(this)).totalDebt;
        if (currentWantInAave > initialDeposit) {
            uint256 interestProfit = currentWantInAave.sub(initialDeposit);
            LENDING_POOL.withdraw(address(want), interestProfit, address(this));
            // Withdraw interest of aToken so that now we have exactly the same amount
        }

        uint256 afterBalance = want.balanceOf(address(this));
        uint256 wantEarned = afterBalance.sub(beforeBalance); // Earned before repaying debt

        // Pay off any debt
        // Debt is equal to negative of canBorrow
        uint256 toRepay = debtBelowHealth();
        uint256 repayAmount = toRepay;

        if (toRepay > wantEarned) {
            // We lost some money, and can only repay up to wantEarned
            repayAmount = wantEarned;
            // Repay all we can, rest is loss
            _loss = toRepay.sub(repayAmount);
            // Notice that once the strats starts loosing funds here, you should probably retire it as it's not profitable
        } else {
            // We made money or are even
            // Let's repay the debtBelowHealth, rest is profit
            _profit = wantEarned.sub(repayAmount);
        }

        if (repayAmount > 0) {
            LENDING_POOL.repay(
                address(want),
                repayAmount,
                VARIABLE_RATE,
                address(this)
            );
        }
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        // Do something to invest excess `want` tokens (from the Vault) into your positions
        // NOTE: Try to adjust positions so that `_debtOutstanding` can be freed up on *next* harvest (not immediately)
        uint256 wantAvailable = want.balanceOf(address(this));
        if (wantAvailable > _debtOutstanding) {
            uint256 toDeposit = wantAvailable.sub(_debtOutstanding);
            LENDING_POOL.deposit(
                address(want),
                toDeposit,
                address(this),
                REFERRAL_CODE
            );

            // Lever up
            _invest();
        }
    }

    function balanceOfRewards() public view returns (uint256) {
        // Get rewards
        address[] memory assets = new address[](2);
        assets[0] = address(aToken);
        assets[1] = address(vToken);

        uint256 totalRewards =
            INCENTIVES_CONTROLLER.getRewardsBalance(assets, address(this));
        return totalRewards;
    }

    function valueOfAAVEToWant(uint256 aaveAmount)
        public
        view
        returns (uint256)
    {
        return ethToWant(AAVEToETH(aaveAmount));
    }

    function valueOfRewards() public view returns (uint256) {
        return valueOfAAVEToWant(balanceOfRewards());
    }

    // Get stkAAVE
    function _claimRewards() internal {
        // Get rewards
        address[] memory assets = new address[](2);
        assets[0] = address(aToken);
        assets[1] = address(vToken);

        // Get Rewards, withdraw all
        INCENTIVES_CONTROLLER.claimRewards(
            assets,
            type(uint256).max,
            address(this)
        );
    }

    function _fromSTKAAVEToAAVE(uint256 rewardsAmount, uint256 minOut)
        internal
    {
        // Swap Rewards in UNIV3
        // NOTE: Unoptimized, can be frontrun and most importantly this pool is low liquidity
        ISwapRouter.ExactInputSingleParams memory fromRewardToAAVEParams =
            ISwapRouter.ExactInputSingleParams(
                address(reward),
                address(AAVE_TOKEN),
                10000,
                address(this),
                now,
                rewardsAmount, // wei
                minOut,
                0
            );
        ROUTER.exactInputSingle(fromRewardToAAVEParams);
    }

    function _fromAAVEToWant(uint256 amountIn, uint256 minOut) internal {
        // We now have AAVE tokens, let's get want
        bytes memory path =
            abi.encodePacked(
                address(AAVE_TOKEN),
                uint24(10000),
                address(WETH_TOKEN),
                uint24(10000),
                address(want)
            );

        ISwapRouter.ExactInputParams memory fromAAVETowBTCParams =
            ISwapRouter.ExactInputParams(
                path,
                address(this),
                now,
                amountIn,
                minOut
            );
        ROUTER.exactInput(fromAAVETowBTCParams);
    }

    function _claimRewardsAndGetMoreWant() internal {
        _claimRewards();

        uint256 rewardsAmount = reward.balanceOf(address(this));

        if (rewardsAmount == 0) {
            return;
        }

        // Specify a min out
        uint256 minAAVEOut = rewardsAmount.mul(minStkAAVEPRice).div(MAX_BPS);
        _fromSTKAAVEToAAVE(rewardsAmount, minAAVEOut);

        uint256 aaveToSwap = AAVE_TOKEN.balanceOf(address(this));

        uint256 minWantOut = 0;
        if (checkSlippageOnHarvest) {
            minWantOut = valueOfAAVEToWant(aaveToSwap)
                .mul(minAAVEToWantPrice)
                .div(MAX_BPS);
        }

        _fromAAVEToWant(aaveToSwap, minWantOut);
    }

    function liquidatePosition(uint256 _amountNeeded)
        internal
        override
        returns (uint256 _liquidatedAmount, uint256 _loss)
    {
        // Do stuff here to free up to `_amountNeeded` from all positions back into `want`
        // NOTE: Maintain invariant `want.balanceOf(this) >= _liquidatedAmount`
        // NOTE: Maintain invariant `_liquidatedAmount + _loss <= _amountNeeded`

        // Lever Down
        _divestFromAAVE();

        uint256 totalAssets = want.balanceOf(address(this));
        if (_amountNeeded > totalAssets) {
            _liquidatedAmount = totalAssets;
            _loss = _amountNeeded.sub(totalAssets);
        } else {
            _liquidatedAmount = _amountNeeded;
        }
    }

    // Withdraw all from AAVE Pool
    function liquidateAllPositions() internal override returns (uint256) {
        // Repay all debt and divest
        _divestFromAAVE();

        // Get rewards before leaving
        _claimRewardsAndGetMoreWant();

        // Return amount freed
        return want.balanceOf(address(this));
    }

    // NOTE: Can override `tendTrigger` and `harvestTrigger` if necessary

    function prepareMigration(address _newStrategy) internal override {
        // Transfer any non-`want` tokens to the new strategy
        // NOTE: `migrate` will automatically forward all `want` in this strategy to the new one
        // This is gone if we use upgradeable

        //Divest all
        _divestFromAAVE();

        if (harvestBeforeMigrate) {
            // Harvest rewards one last time
            _claimRewardsAndGetMoreWant();
        }

        // Just in case we don't fully liquidate to want
        if (aToken.balanceOf(address(this)) > 0) {
            aToken.safeTransfer(_newStrategy, aToken.balanceOf(address(this)));
        }

        if (reward.balanceOf(address(this)) > 0) {
            reward.safeTransfer(_newStrategy, reward.balanceOf(address(this)));
        }

        if (AAVE_TOKEN.balanceOf(address(this)) > 0) {
            AAVE_TOKEN.safeTransfer(
                _newStrategy,
                AAVE_TOKEN.balanceOf(address(this))
            );
        }
    }

    // Override this to add all tokens/tokenized positions this contract manages
    // on a *persistent* basis (e.g. not just for swapping back to want ephemerally)
    // NOTE: Do *not* include `want`, already included in `sweep` below
    //
    // Example:
    //
    //    function protectedTokens() internal override view returns (address[] memory) {
    //      address[] memory protected = new address[](3);
    //      protected[0] = tokenA;
    //      protected[1] = tokenB;
    //      protected[2] = tokenC;
    //      return protected;
    //    }
    function protectedTokens()
        internal
        view
        override
        returns (address[] memory)
    {
        address[] memory protected = new address[](3);
        protected[0] = address(aToken);
        protected[1] = address(reward);
        protected[2] = address(AAVE_TOKEN);
        return protected;
    }

    /**
     * @notice
     *  Provide an accurate conversion from `_amtInWei` (denominated in wei)
     *  to `want` (using the native decimal characteristics of `want`).
     * @dev
     *  Care must be taken when working with decimals to assure that the conversion
     *  is compatible. As an example:
     *
     *      given 1e17 wei (0.1 ETH) as input, and want is USDC (6 decimals),
     *      with USDC/ETH = 1800, this should give back 1800000000 (180 USDC)
     *
     * @param _amtInWei The amount (in wei/1e-18 ETH) to convert to `want`
     * @return The amount in `want` of `_amtInEth` converted to `want`
     **/
    function ethToWant(uint256 _amtInWei)
        public
        view
        virtual
        override
        returns (uint256)
    {
        address priceOracle = ADDRESS_PROVIDER.getPriceOracle();
        uint256 priceInEth =
            IPriceOracle(priceOracle).getAssetPrice(address(want));

        // Opposite of priceInEth
        // Multiply first to keep rounding
        uint256 priceInWant = _amtInWei.mul(10**DECIMALS).div(priceInEth);

        return priceInWant;
    }

    function AAVEToETH(uint256 _amt) public view returns (uint256) {
        address priceOracle = ADDRESS_PROVIDER.getPriceOracle();
        uint256 priceInEth =
            IPriceOracle(priceOracle).getAssetPrice(address(AAVE_TOKEN));

        // Price in ETH
        // AMT * Price in ETH / Decimals
        uint256 aaveToEth = _amt.mul(priceInEth).div(10**18);

        return aaveToEth;
    }

    /* Leverage functions */
    function deposited() public view returns (uint256) {
        return aToken.balanceOf(address(this));
    }

    function borrowed() public view returns (uint256) {
        return vToken.balanceOf(address(this));
    }

    // What should we repay?
    function debtBelowHealth() public view returns (uint256) {
        (, , , , uint256 ltv, uint256 healthFactor) =
            LENDING_POOL.getUserAccountData(address(this));

        // How much did we go off of minHealth? //NOTE: We always borrow as much as we can
        uint256 maxBorrow = deposited().mul(ltv).div(MAX_BPS);

        uint256 allDebt = borrowed();

        if (healthFactor < minHealth && allDebt > maxBorrow) {
            uint256 maxValue = allDebt.sub(maxBorrow);

            return maxValue;
        }

        return 0;
    }

    // NOTE: We always borrow max, no fucks given
    function canBorrow() public view returns (uint256) {
        (, , , , uint256 ltv, uint256 healthFactor) =
            LENDING_POOL.getUserAccountData(address(this));

        if (healthFactor > minHealth) {
            // Amount = deposited * ltv - borrowed
            // Div MAX_BPS because because ltv / maxbps is the percent
            uint256 maxValue =
                deposited().mul(ltv).div(MAX_BPS).sub(borrowed());

            // Don't borrow if it's dust, save gas
            if (maxValue < minRebalanceAmount) {
                return 0;
            }

            return maxValue;
        }

        return 0;
    }

    function _invest() internal {
        // Loop on it until it's properly done
        for (uint256 i = 0; i < maxIterations; i++) {
            uint256 toBorrow = canBorrow();
            if (toBorrow > 0) {
                LENDING_POOL.borrow(
                    address(want),
                    toBorrow,
                    VARIABLE_RATE,
                    REFERRAL_CODE,
                    address(this)
                );

                LENDING_POOL.deposit(
                    address(want),
                    toBorrow,
                    address(this),
                    REFERRAL_CODE
                );
            } else {
                break;
            }
        }
    }

    // Divest all from AAVE, awful gas, but hey, it works
    function _divestFromAAVE() internal {
        (bool shouldRepay, uint256 repayAmount) = canRepay(); // The "unsafe" (below target health) you can withdraw

        // Loop to withdraw until you have the amount you need
        while (shouldRepay) {
            _withdrawStepFromAAVE(repayAmount);
            (shouldRepay, repayAmount) = canRepay();
        }
        if (deposited() > 0) {
            // Withdraw the rest here
            LENDING_POOL.withdraw(
                address(want),
                type(uint256).max,
                address(this)
            );
        }
    }

    // Withdraw and Repay AAVE Debt
    function _withdrawStepFromAAVE(uint256 repayAmount) internal {
        if (repayAmount > 0) {
            //Repay this step
            LENDING_POOL.withdraw(address(want), repayAmount, address(this));
            LENDING_POOL.repay(
                address(want),
                repayAmount,
                VARIABLE_RATE,
                address(this)
            );
        }
    }

    // returns 95% of the collateral we can withdraw from aave, used to loop and repay debts
    // You always can repay something, if we return false, it means you have nothing to pay
    function canRepay() public view returns (bool, uint256) {
        (
            uint256 totalCollateralETH,
            uint256 totalDebtETH,
            uint256 availableBorrowsETH,
            uint256 currentLiquidationThreshold,
            uint256 ltv,
            uint256 healthFactor
        ) = LENDING_POOL.getUserAccountData(address(this));

        uint256 aBalance = deposited();
        uint256 vBalance = borrowed();

        if (vBalance == 0) {
            return (false, 0); //You have repaid all
        }

        uint256 diff =
            aBalance.sub(
                vBalance.mul(MAX_BPS).div(currentLiquidationThreshold)
            );
        uint256 inWant = diff.mul(95).div(100); // Take 95% just to be safe

        return (true, inWant);
    }

    /** Manual Functions */

    /** Leverage Manual Functions */
    // Emergency function to immediately deleverage to 0
    function manualDivestFromAAVE() public onlyVaultManagers {
        _divestFromAAVE();
    }

    // Manually perform 5 loops to lever up
    // Safe because it's capped by canBorrow
    function manualLeverUp() public onlyVaultManagers {
        _invest();
    }

    // Emergency function that we can use to deleverage manually if something is broken
    // If something goes wrong, just try smaller and smaller can repay amounts
    function manualWithdrawStepFromAAVE(uint256 toRepay)
        public
        onlyVaultManagers
    {
        _withdrawStepFromAAVE(toRepay);
    }

    // Take some funds from manager and use them to repay
    // Useful if you ever go below 1 HF and somehow you didn't get liquidated
    function manualRepayFromManager(uint256 toRepay) public onlyVaultManagers {
        want.safeTransferFrom(msg.sender, address(this), toRepay);
        LENDING_POOL.repay(
            address(want),
            toRepay,
            VARIABLE_RATE,
            address(this)
        );
    }

    /** DCA Manual Functions */

    // Get the rewards
    function manualClaimRewards() public onlyVaultManagers {
        _claimRewards();
    }

    // Initiate 10 days cooldown period manually
    // You can use this if you believe V3 Pool is too illiquid
    function manualCooldownRewards() public onlyVaultManagers {
        IStakedAave stkAAVE = IStakedAave(address(reward));
        stkAAVE.claimRewards(address(this), type(uint256).max);
        stkAAVE.cooldown();
    }

    // Manually redeem rewards, claiming AAVE
    // You can use this if you believe V3 Pool is too illiquid
    function manualRedeemRewards() public onlyVaultManagers {
        IStakedAave stkAAVE = IStakedAave(address(reward));
        stkAAVE.claimRewards(address(this), type(uint256).max);
        stkAAVE.redeem(address(this), type(uint256).max);
    }

    // Swap from stkAAVE to AAVE
    ///@param amountToSwap Amount of stkAAVE to Swap, NOTE: You have to calculate the amount!!
    ///@param multiplierInWei pricePerToken including slippage, will be divided by 10 ** 18
    function manualSwapFromStkAAVEToAAVE(
        uint256 amountToSwap,
        uint256 multiplierInWei
    ) public onlyVaultManagers {
        uint256 amountOutMinimum =
            amountToSwap.mul(multiplierInWei).div(10**18);

        _fromSTKAAVEToAAVE(amountToSwap, amountOutMinimum);
    }

    // Swap from AAVE to Want
    ///@param amountToSwap Amount of AAVE to Swap, NOTE: You have to calculate the amount!!
    ///@param multiplierInWei pricePerToken including slippage, will be divided by 10 ** 18
    function manualSwapFromAAVEToWant(
        uint256 amountToSwap,
        uint256 multiplierInWei
    ) public onlyVaultManagers {
        uint256 amountOutMinimum =
            amountToSwap.mul(multiplierInWei).div(10**18);

        _fromAAVEToWant(amountToSwap, amountOutMinimum);
    }
}

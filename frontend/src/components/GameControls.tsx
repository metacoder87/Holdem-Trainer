import { useState } from "react";
import { submitGameInput, type PendingInput } from "../api/client";

interface GameControlsProps {
    sessionId: string;
    pendingInput: PendingInput | null;
    onAction: () => void;
}

export default function GameControls({ sessionId, pendingInput, onAction }: GameControlsProps) {
    const [betAmount, setBetAmount] = useState<string>("");

    if (!pendingInput) {
        return <div className="game-controls waiting">Waiting for action...</div>;
    }

    const submitInput = async (payload: { choice?: number; value?: number | boolean }) => {
        try {
            await submitGameInput(sessionId, payload);
            setBetAmount("");
            onAction();
        } catch (err) {
            console.error("Failed to submit input:", err);
        }
    };

    if (pendingInput.kind === 'menu' && pendingInput.options?.length) {
        return (
            <div className="game-controls">
                <div className="game-control-prompt">{pendingInput.prompt}</div>
                <div className="game-control-row">
                {pendingInput.options.map((option, idx) => {
                    let btnClass = "btn secondary";
                    if (option.toLowerCase().includes("fold")) btnClass = "btn danger";
                    if (option.toLowerCase().includes("raise") || option.toLowerCase().includes("bet")) btnClass = "btn primary";

                    // API expects 1-based index for menu choices
                    return (
                        <button key={option} onClick={() => submitInput({ choice: idx + 1 })} className={btnClass}>
                            {option}
                        </button>
                    );
                })}
                </div>
            </div>
        );
    }

    if (pendingInput.kind === 'number') {
        const minValue = pendingInput.min_value ?? undefined;
        const maxValue = pendingInput.max_value ?? undefined;
        return (
            <div className="game-controls">
                <div className="game-control-prompt">{pendingInput.prompt}</div>
                <div className="game-control-row number-entry">
                    <input
                        type="number"
                        className="control-input"
                        placeholder={minValue !== undefined ? `Min: ${minValue}` : "Amount"}
                        value={betAmount}
                        onChange={(event) => setBetAmount(event.target.value)}
                        min={minValue}
                        max={maxValue}
                    />
                    <button
                        className="btn primary"
                        onClick={() => submitInput({ value: Number(betAmount) })}
                        disabled={!betAmount}
                    >
                        Submit
                    </button>
                </div>
                {minValue !== undefined && (
                    <div className="game-control-hint">
                        {minValue} - {maxValue ?? "No max"}
                    </div>
                )}
            </div>
        );
    }

    if (pendingInput.kind === 'yes_no') {
        return (
            <div className="game-controls">
                <div className="game-control-prompt">{pendingInput.prompt}</div>
                <div className="game-control-row">
                <button className="btn primary" onClick={() => submitInput({ value: true })}>Yes</button>
                <button className="btn secondary" onClick={() => submitInput({ value: false })}>No</button>
                </div>
            </div>
        )
    }

    return <div className="game-controls error">Unknown input request: {pendingInput.kind}</div>;
}

#!/usr/bin/env python3
"""
Training Mode Demo for PyHoldem Pro
Demonstrates the interactive training features.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from training.trainer import PokerTrainer, QuizType
from training.analyzer import HandAnalyzer, SessionReviewer
from training.hud import TrainerHUD
from training.content_loader import ContentLoader
from game.player import Player, PlayerAction


def demo_quiz_system():
    """Demonstrate the interactive quiz system."""
    print("🎓 PYHOLDEM PRO TRAINING MODE DEMO")
    print("=" * 50)
    
    trainer = PokerTrainer()
    trainer.enable_training()
    
    # Demo pot odds quiz
    print("\n📊 POT ODDS QUIZ DEMO:")
    quiz = trainer.generate_quiz(QuizType.POT_ODDS, pot_size=200, bet_to_call=50)
    print(quiz['question'])
    print(f"\nCorrect Answer: {quiz['correct_answer']:.3f} ({quiz['correct_percentage']}%)")
    print(quiz['explanation'])
    
    # Demo user answer evaluation
    print("\n🧮 ANSWER EVALUATION DEMO:")
    result = trainer.evaluate_answer(quiz['correct_answer'], 0.20, tolerance=0.01)
    print(f"User Answer: 20%")
    print(f"Evaluation: {result['feedback']}")
    
    # Show performance stats
    print("\n📈 PERFORMANCE TRACKING:")
    performance = trainer.get_performance_summary()
    print(f"Accuracy: {performance['accuracy']:.1f}%")
    print(f"Grade: {performance['grade']} - {performance['message']}")


def demo_hand_analysis():
    """Demonstrate post-hand analysis."""
    print("\n\n🔍 HAND ANALYSIS DEMO:")
    print("=" * 30)
    
    analyzer = HandAnalyzer()
    
    # Demo decision analysis
    analysis = analyzer.analyze_decision(
        action=PlayerAction.CALL,
        pot_size=150,
        bet_to_call=50,
        hand_equity=0.35,
        opponent_type="tight-aggressive"
    )
    
    print("📋 DECISION ANALYSIS:")
    print(f"Action: {analysis['action_taken']}")
    print(f"Pot Odds: {analysis['pot_odds_percentage']:.1f}%")
    print(f"Hand Equity: {analysis['hand_equity_percentage']:.1f}%")
    print(f"Recommendation: {analysis['recommendation'].upper()}")
    print(f"\n💭 REASONING:\n{analysis['reasoning']}")
    
    # Demo bluff analysis
    print("\n🃏 BLUFF ANALYSIS:")
    bluff_analysis = analyzer.analyze_bluff(75, 100, "tight-passive", "dry")
    print(f"Against tight player on dry board:")
    print(f"Expected Value: ${bluff_analysis['expected_value']:.0f}")
    print(f"Profitable: {'YES' if bluff_analysis['profitability'] else 'NO'}")


def demo_session_review():
    """Demonstrate session review functionality."""
    print("\n\n📊 SESSION REVIEW DEMO:")
    print("=" * 30)
    
    reviewer = SessionReviewer()
    
    # Sample session data
    session_data = {
        'hands_played': 150,
        'vpip': 0.32,  # Too high
        'pfr': 0.08,   # Too low
        'aggression_factor': 1.1,  # Too passive
        'net_result': -250,
        'position_stats': {
            'early_position': {'hands': 45, 'vpip': 18, 'pfr': 4},
            'late_position': {'hands': 50, 'vpip': 25, 'pfr': 8}
        }
    }
    
    report = reviewer.generate_session_report(session_data)
    
    print("📈 SESSION SUMMARY:")
    summary = report['session_summary']
    print(f"Hands Played: {summary['hands_played']}")
    print(f"Net Result: ${summary['net_result']}")
    print(f"BB/100: {summary['bb_per_100']:.1f}")
    
    print(f"\n🎯 OVERALL GRADE: {report['overall_grade']['letter']} ({report['overall_grade']['percentage']:.1f}%)")
    
    print("\n🚨 IDENTIFIED LEAKS:")
    for leak in report['identified_leaks']:
        severity_icon = "🔴" if leak['severity'] == 'high' else "🟡"
        print(f"{severity_icon} {leak['description']}")
        
    print("\n💡 RECOMMENDATIONS:")
    for i, suggestion in enumerate(report['recommendations'][:3], 1):
        print(f"{i}. {suggestion['action']}")
        print(f"   Why: {suggestion['reason']}")


def demo_hud_display():
    """Demonstrate HUD functionality."""
    print("\n\n💻 TRAINER HUD DEMO:")
    print("=" * 25)
    
    hud = TrainerHUD()
    hud.enable()
    
    # Sample opponent data
    opponent_stats = {
        'AI_Tight': {'vpip': 0.18, 'pfr': 0.15, 'af': 2.2, 'type': 'tight-aggressive'},
        'AI_Loose': {'vpip': 0.42, 'pfr': 0.08, 'af': 1.1, 'type': 'loose-passive'},
        'AI_Wild': {'vpip': 0.38, 'pfr': 0.28, 'af': 3.5, 'type': 'loose-aggressive'}
    }
    
    hud.update_opponent_stats(opponent_stats)
    
    # Sample game situation
    current_stats = {
        'pot_size': 180,
        'bet_to_call': 60,
        'hand_equity': 0.28,
        'required_equity': 0.25
    }
    
    hud.update_current_stats(current_stats)
    
    print("🎯 OPPONENT ANALYSIS:")
    for opponent, stats in opponent_stats.items():
        display = hud.format_opponent_display(opponent, stats)
        print(f"  {display}")
        
    print("\n💰 POT ODDS:")
    pot_display = hud.generate_pot_odds_display(180, 60)
    print(f"  {pot_display}")
    
    print("\n📊 EQUITY ANALYSIS:")
    equity_display = hud.generate_equity_display(0.28, 0.25)
    print(f"  {equity_display}")


def demo_educational_content():
    """Demonstrate educational content system."""
    print("\n\n📚 EDUCATIONAL CONTENT DEMO:")
    print("=" * 35)
    
    loader = ContentLoader()
    
    # Show a random tip
    print("💡 RANDOM POKER TIP:")
    tip = loader.get_random_tip()
    print(f"📖 {tip['title']}")
    print(f"💭 {tip['content'][:150]}...")
    
    # Show vocabulary
    print("\n📖 POKER VOCABULARY SAMPLE:")
    vocab = loader.load_vocabulary()
    for term in vocab[:2]:
        print(f"🔤 {term['term']}: {term['definition']}")
        
    # Show cheat sheet
    print("\n📋 STARTING HANDS CHEAT SHEET:")
    cheat_sheets = loader.load_cheat_sheets()
    starting_hands = cheat_sheets.get('starting_hands', {})
    print(f"💎 Premium: {', '.join(starting_hands.get('premium', []))}")
    print(f"⭐ Strong: {', '.join(starting_hands.get('strong', []))}")


def main():
    """Run the complete training demo."""
    print("🎲 Welcome to PyHoldem Pro Training Mode Demo! 🎲")
    
    try:
        demo_quiz_system()
        demo_hand_analysis()
        demo_session_review()
        demo_hud_display()
        demo_educational_content()
        
        print("\n\n🎉 DEMO COMPLETE!")
        print("=" * 50)
        print("🎓 PyHoldem Pro Training Mode Features:")
        print("  ✅ Interactive quizzes with adaptive difficulty")
        print("  ✅ Real-time hand analysis and feedback")  
        print("  ✅ Comprehensive session reviews")
        print("  ✅ Live opponent statistics HUD")
        print("  ✅ Educational content library")
        print("  ✅ Personalized improvement recommendations")
        print("\n💡 Ready to make you a better poker player!")
        
    except Exception as e:
        print(f"❌ Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

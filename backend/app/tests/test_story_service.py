from app.services.story import StoryService


class DummyGemini:
    def generate_story_step(self, **kwargs):
        step = kwargs['step_number']
        if step <= 3:
            return {
                'narrative': f'Narrative step {step}',
                'options': [f'Option {step}A', f'Option {step}B', f'Option {step}C'],
            }
        return {'ending': 'Final ending'}

    def score_theme_coverage(self, **kwargs):
        return {
            'score_total': 88,
            'breakdown': {
                'complaint_coverage': 90,
                'preference_satisfaction': 84,
                'coherence': 89,
            },
            'per_cluster': [],
        }


def test_story_service_three_step_flow() -> None:
    service = StoryService(DummyGemini())
    story_id, narrative, options, step = service.start_story(
        movie_id='tt123',
        movie_title='Test Movie',
        what_if='What if the hero stayed?',
        plot_context='Plot context',
        beats=[],
        clusters=[],
        user_session_id='sess-1',
    )

    assert step == 1
    assert narrative == 'Narrative step 1'
    assert len(options) == 3

    step_two = service.continue_story(
        story_session_id=story_id,
        option_id=options[0].option_id,
        user_session_id='sess-1',
    )
    assert step_two['step_number'] == 2

    step_three = service.continue_story(
        story_session_id=story_id,
        option_id=step_two['options'][0].option_id,
        user_session_id='sess-1',
    )
    assert step_three['step_number'] == 3

    final = service.continue_story(
        story_session_id=story_id,
        option_id=step_three['options'][0].option_id,
        user_session_id='sess-1',
    )
    assert final['is_complete'] is True
    assert final['ending'] == 'Final ending'

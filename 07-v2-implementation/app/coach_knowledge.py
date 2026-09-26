"""Small reviewed reference set. Summaries are guidance, not athlete-specific proof."""
REFERENCES = {
    'science_load': {
        'title': 'Monitoring Athlete Training Loads: Consensus Statement (2017)',
        'url': 'https://pubmed.ncbi.nlm.nih.gov/28463642/',
        'summary': 'Interpret training using both external work and the athlete’s response. Multiple measures and their trends provide context that a single score cannot.',
        'limits': 'General monitoring guidance. It does not establish the cause of this athlete’s fatigue or validate a fixed reduction rule.',
    },
    'science_weather': {
        'title': 'Impact of environmental parameters on marathon running performance (2012)',
        'url': 'https://pubmed.ncbi.nlm.nih.gov/22649525/',
        'summary': 'A large observational marathon study associated warmer conditions above performance-dependent optima with slower performance.',
        'limits': 'Population associations do not supply an exact personal heat penalty. Course, adaptation and reference-race conditions matter.',
    },
    'science_prediction': {
        'title': 'An empirical study of race times in recreational endurance runners (2016)',
        'url': 'https://pubmed.ncbi.nlm.nih.gov/27570626/',
        'summary': 'Race results and training information can inform estimates. Simple short-race equivalence often predicts marathon times too optimistically for recreational runners.',
        'limits': 'This app’s forecast is a heuristic, not the study’s validated model. Finishing training does not guarantee a future performance.',
    },
    'science_wellbeing': {
        'title': 'Monitoring the athlete training response: subjective self-reported measures (2016)',
        'url': 'https://pubmed.ncbi.nlm.nih.gov/26423706/',
        'summary': 'A systematic review found subjective wellbeing useful for monitoring responses to training. How an athlete feels adds information to wearable measurements.',
        'limits': 'A single difficult session does not diagnose overtraining. Relative Effort is not a subjective wellbeing report.',
    },
}


def retrieve(question):
    q=question.lower()
    ids=['science_load','science_wellbeing']
    if any(word in q for word in ('race','marathon','improv','faster','plateau','fitness')): ids.append('science_prediction')
    if any(word in q for word in ('weather','heat','hot','humid','race')): ids.append('science_weather')
    return {key:REFERENCES[key] for key in ids}

// Static content for the Topics, Contacts and Calendar screens.
// Source: the AITU knowledge base used by the assistant (snapshot 2026-10-21).

class Topic {
  const Topic(this.name, this.count, this.questions);
  final String name;
  final int count;
  final List<String> questions;
}

const kTopics = <Topic>[
  Topic('Certificates & procedures', 25, [
    'How do I order a transcript?',
    'How can I get an enrollment certificate?',
  ]),
  Topic('Policy & calendar', 15, [
    'When does the winter exam session start?',
    'What are the rules for retaking an exam?',
  ]),
  Topic('Services & student life', 25, [
    'How do I extend a library loan?',
    'Where is the medical room?',
  ]),
  Topic('Career & research', 25, [
    'How can I find an internship?',
    'How do I join a research project?',
  ]),
  Topic('Departments', 20, [
    'Who do I contact at the Registrar\'s Office?',
    'Where is the Student Department?',
  ]),
  Topic('Admission & AET', 25, [
    'What is the AET and who has to take it?',
    'Which documents do applicants need?',
  ]),
  Topic('Schools & programs', 56, [
    'Which programs does the school of IT offer?',
    'How long is the bachelor program?',
  ]),
  Topic('Tuition & discounts', 9, [
    'Are there tuition discounts?',
    'How do I pay for the semester?',
  ]),
];

const kCommonQuestions = <String>[
  'How do I extend a library loan?',
  'How do I order a transcript?',
  'When does the winter exam session start?',
  'Who do I contact for IT help?',
];

class Contact {
  const Contact(this.name, this.detail, {this.email, this.room, this.phone});
  final String name;
  final String detail;
  final String? email;
  final String? room;
  final String? phone;
}

const kContacts = <Contact>[
  Contact('Student Department', 'Student questions and documents', room: 'C1.1.273'),
  Contact('Transcript requests', 'Ordering transcripts', email: 'transcript@astanait.edu.kz'),
  Contact('Student support', 'Distance learning support', email: 'support_du@astanait.edu.kz'),
  Contact('IT Helpdesk', 'Accounts, Wi-Fi, systems', email: 'helpdesk@astanait.edu.kz', room: 'C1.2.255'),
  Contact('Registrar\'s Office', 'Registration and records', email: 'office.reg@astanait.edu.kz', room: 'C1.1.270'),
  Contact('Medical room', 'First aid', room: '8', phone: '8 (7172) 64-57-33'),
];

class Period {
  const Period(this.name, this.start, this.end, {this.exam = false});
  final String name;
  final DateTime start;
  final DateTime end;
  final bool exam;
}

/// Year 2, bachelor, academic year 2026-27.
final kPeriods = <Period>[
  Period('Fall - theoretical study', DateTime(2026, 9, 7), DateTime(2026, 11, 14)),
  Period('Fall - exam session', DateTime(2026, 11, 16), DateTime(2026, 11, 28), exam: true),
  Period('Winter - theoretical study', DateTime(2026, 12, 7), DateTime(2027, 2, 13)),
  Period('Winter - exam session', DateTime(2027, 2, 15), DateTime(2027, 2, 27), exam: true),
  Period('Spring - theoretical study', DateTime(2027, 3, 15), DateTime(2027, 5, 22)),
];

String fmtDate(DateTime d) {
  String two(int n) => n.toString().padLeft(2, '0');
  return '${d.year}-${two(d.month)}-${two(d.day)}';
}

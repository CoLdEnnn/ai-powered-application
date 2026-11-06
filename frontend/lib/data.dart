// Static content for the Topics and Contacts screens.
// Topics are counted from the current knowledge base (rag_student_final_en.jsonl, 224 passages).
// Contacts are checked against the same knowledge base.

class Topic {
  const Topic(this.name, this.count, this.questions);
  final String name;
  final int count;
  final List<String> questions;
}

const kTopics = <Topic>[
  Topic('Academic and administrative procedures', 32, [
    'How long is a Bachelor\'s programme under Academic Policy Edition 4?',
    'How many trimesters are there in an AITU academic year?',
    'How long is a trimester?',
  ]),
  Topic('Schools and programme catalogues', 27, [
    'What is the language of instruction for bachelor\'s programmes?',
    'How long is a master\'s degree and what is the language of instruction?',
    'Which main master\'s programmes are listed at AITU?',
  ]),
  Topic('Detailed programme pages', 26, [
    'What is the focus of the Mathematical and Computational Science programme (bachelor\'s)?',
    'What is the focus of the Cybersecurity programme (bachelor\'s)?',
    'What is the focus of the Smart Security Technologies programme (bachelor\'s)?',
  ]),
  Topic('Services and student life', 25, [
    'What room types are available in AITU student residences?',
    'Where is cooking allowed in the dormitory?',
    'Do the dormitories have Wi-Fi and laundry facilities?',
  ]),
  Topic('Mobility, careers and research', 24, [
    'What is outgoing academic mobility at AITU?',
    'Which documents are listed for outgoing academic mobility?',
    'Who receives preference when applicants have equal scores in the mobility selection process?',
  ]),
  Topic('Student residence procedures and payments', 18, [
    'How do I apply for AITU dormitory accommodation using My DU?',
    'How can I track my dormitory application?',
    'How do I choose a dormitory room after my application is reviewed?',
  ]),
  Topic('Fees and tariffs', 17, [
    'How much does one Retake/FX credit cost for AITU bachelor’s students in 2026–2027?',
    'How much does one credit cost for bachelor’s transfer, reinstatement, repeat-year study, or curriculum differences in 2026–2027?',
    'Can a student receive two AITU discounts at the same time?',
  ]),
  Topic('Navigation, departments and contacts', 17, [
    'What address is listed for AITU?',
    'How can I contact the AITU administrative office?',
    'How can I contact AITU\'s general Admissions Office?',
  ]),
  Topic('Academic policy, calendar and IGPA', 15, [
    'Who organizes course registration at AITU?',
    'Can an FX final examination be retaken without repeating the course outside the summer semester?',
    'What should a student do after receiving a final grade of F?',
  ]),
  Topic('Grants and tuition discounts', 9, [
    'Where are tuition-discount applications submitted?',
    'Can a fee-paying undergraduate student with strong grades apply for a 30% discount?',
    'What discount is listed for qualifying families with several AITU students or graduates?',
  ]),
];

const kCommonQuestions = <String>[
  'Who organizes course registration at AITU?',
  'How do I apply for AITU dormitory accommodation using My DU?',
  'Where are tuition-discount applications submitted?',
  'Where should I send a transcript request?',
];

/// Questions about the calendar and academic rules (shown on the Calendar screen).
const kCalendarQuestions = <String>[

  'Who organizes course registration at AITU?',
  'Can an FX final examination be retaken without repeating the course outside the summer semester?',
  'What should a student do after receiving a final grade of F?',
  'How long is the summer semester?',
  'How many credits can a student take in the summer semester?',
  'How can a student register for the summer semester?',
  'Is an FX examination retake available in the summer semester?',
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
  Contact('Student Department', 'Student certificates. Head: g.zhussupova@astanait.edu.kz', email: 'g.zhussupova@astanait.edu.kz', room: 'C1.1.273'),
  Contact('Transcript requests', 'Where to send a transcript request', email: 'transcript@astanait.edu.kz'),
  Contact('Technical support: DU, Moodle, Abitur', 'Problems with DU, Moodle or Abitur', email: 'support_du@astanait.edu.kz'),
  Contact('IT helpdesk', 'Other technical questions', email: 'helpdesk@astanait.edu.kz', room: 'C1.2.255 (head and administrators)'),
  Contact('Registrar\'s Office', 'Course registration and academic records. Head: Aliya.Koitanova@astanait.edu.kz', email: 'Aliya.Koitanova@astanait.edu.kz', room: 'C1.1.270'),
  Contact('Library', 'Library questions', email: 'library@astanait.edu.kz', phone: '+7 (7172) 64-57-17'),
  Contact('Administrative office', 'General contacts (confirm availability on the official Contacts page)', email: 'info@astanait.edu.kz', phone: '+7 (7172) 645-728'),
];

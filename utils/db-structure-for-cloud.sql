***** OUT OF DATE *****

drop table if exists questions;
create table questions (
  id int,
  title varchar(255),
  question varchar(255),
  nickname_authentication tinyint default 0,
  user_id int,
  phase int default 0,
  cascade_step int default 0,  *****NEW*****
  cascade_k int default 5,
  cascade_m int default 32,
  cascade_t int default 8,
  last_update timestamp not null default current_timestamp on update current_timestamp,
  primary key(id),
  key user_index (user_id)  *****NEW*****
) engine=InnoDB default charset=utf8;

drop table if exists question_ideas;
create table question_ideas (
  id int auto_increment,
  question_id int,
  user_id int,
  idea varchar(255),
  created_on timestamp default current_timestamp,
  primary key(id),
  key question_index (question_id)
) engine=InnoDb default charset=utf8;

drop table if exists users;
create table users (
  id int auto_increment,
  authenticated_user_id varchar(255),
  authenticated_nickname varchar(255),
  nickname varchar(50) DEFAULT NULL,
  question_id int(11) DEFAULT NULL,
  latest_login_timestamp timestamp null default null,
  latest_logout_timestamp timestamp null default null,
  primary key(id),
  key question_index(question_id)
) engine=InnoDB default charset=utf8;

drop table if exists user_clients;
create table user_clients (
  user_id int(11),
  client_id varchar(255)
) engine=InnoDB default charset=utf8;

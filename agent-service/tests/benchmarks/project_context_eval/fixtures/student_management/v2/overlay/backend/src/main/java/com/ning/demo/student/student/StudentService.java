package com.ning.demo.student.student;

import com.ning.demo.student.common.StudentNotFoundException;
import org.springframework.stereotype.Service;

import java.util.List;

/** v2 学生档案业务编排。 */
@Service
public class StudentService {

    private final StudentRepository repository;

    public StudentService(StudentRepository repository) {
        this.repository = repository;
    }

    public List<Student> list(String name) {
        return name == null || name.isBlank() ? repository.findAll() : repository.searchByName(name.trim());
    }

    public Student get(long id) {
        return repository.findById(id).orElseThrow(StudentNotFoundException::new);
    }

    public Student create(CreateStudentRequest request) {
        return repository.save(request);
    }

    public Student update(long id, UpdateStudentRequest request) {
        if (repository.update(id, request) == 0) {
            throw new StudentNotFoundException();
        }
        return get(id);
    }
}

